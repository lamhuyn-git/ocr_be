"""
/api/v1/form  — Form template management + form submission & extraction.

Endpoints
---------
POST   /form/templates          Upload & register a new form template  [superuser/admin]
GET    /form/templates          List active templates                   [authenticated]

POST   /form                    Submit image → run pipeline → store     [authenticated]
GET    /form                    List submitted forms (own / all)        [authenticated]
GET    /form/{form_db_id}       Full detail incl. extracted fields      [authenticated]
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

import yaml
from fastapi import (
    APIRouter, BackgroundTasks, Depends, File,
    Form, HTTPException, UploadFile, status,
)
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_current_user, get_current_superuser,
    assert_form_ward_access, get_user_ward_ids, get_user_membership,
)
from app.database import get_db
from app.models.form import (
    Form as FormModel, FormStatus, FormStatusHistory, FormTemplate, REVIEW_PREDECESSORS,
)
from app.models.organization import Organization
from app.models.user import User
from app.schemas.form import (
    DecisionRequest, FormCreateResponse, FormDetailResponse,
    FormList, FormResponse, FormStatusHistoryItem, FormTemplateResponse, ResultRequest,
)
from app.services.form_service import (
    run_form_pipeline, save_template_config, validate_template_yaml,
)
from app.utils.file_utils import save_upload, delete_file, get_file_extension

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/form", tags=["Form"])

_ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "bmp", "tiff", "webp"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def record_status_change(
    db: AsyncSession,
    form: FormModel,
    to_status: FormStatus,
    actor_user_id: UUID | None,
    note: str | None = None,
) -> None:
    """Append a status-transition row and apply the new status to the form.
    Caller is responsible for the surrounding transaction/commit."""
    db.add(
        FormStatusHistory(
            form_id=form.id,
            from_status=form.status,
            to_status=to_status,
            actor_user_id=actor_user_id,
            note=note,
        )
    )
    form.status = to_status


async def _get_form_or_404(form_db_id: UUID, db: AsyncSession) -> FormModel:
    form = await db.get(FormModel, form_db_id)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    return form


async def _get_active_template(form_id: str, db: AsyncSession) -> FormTemplate:
    tmpl = (
        await db.execute(
            select(FormTemplate).where(
                FormTemplate.form_id == form_id,
                FormTemplate.is_active == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not tmpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active template found for form_id='{form_id}'",
        )
    return tmpl


# ── Background task ───────────────────────────────────────────────────────────

async def _process_form_bg(form_db_id: UUID, image_path: str, config_path: str) -> None:
    """Run pipeline in background; update DB when done.

    Lock the row and only transition out of `submitted`/`processing` — never clobber a
    form a human has already moved into the review flow (under_review/approved/...)."""
    from app.database import AsyncSessionLocal

    _RUNNABLE = {FormStatus.submitted, FormStatus.processing}

    async with AsyncSessionLocal() as db:
        form = await db.get(FormModel, form_db_id, with_for_update=True)
        if not form or form.status not in _RUNNABLE:
            await db.rollback()
            return
        record_status_change(db, form, FormStatus.processing, actor_user_id=None, note="OCR started")
        await db.commit()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, run_form_pipeline, image_path, config_path
            )
        except Exception as exc:
            logger.exception("Form pipeline failed for %s", form_db_id)
            async with AsyncSessionLocal() as db2:
                form = await db2.get(FormModel, form_db_id, with_for_update=True)
                if form and form.status == FormStatus.processing:
                    form.error_message = str(exc)
                    record_status_change(db2, form, FormStatus.failed, actor_user_id=None, note="OCR error")
                    await db2.commit()
            return

        async with AsyncSessionLocal() as db2:
            form = await db2.get(FormModel, form_db_id, with_for_update=True)
            if not form or form.status != FormStatus.processing:
                await db2.rollback()
                return
            form.extracted_fields   = result["extracted_fields"]
            form.validated_fields   = result["validated_fields"]
            form.confidence_score   = result["confidence_score"]
            form.alignment_method   = result["alignment_method"]
            form.alignment_quality  = result["alignment_quality"]
            form.alignment_meta     = result["alignment_meta"]
            form.processing_time_ms = result["processing_time_ms"]
            record_status_change(db2, form, FormStatus.extracted, actor_user_id=None, note="OCR completed")
            await db2.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATE endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/templates",
    response_model=FormTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Upload & register a new form template",
)
async def create_template(
    name: str = Form(..., description="Human-readable template name, e.g. 'Đơn CT-01'"),
    config_file: UploadFile = File(..., description="YAML config file validated against ct01 schema"),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a YAML template config.
    - Validates against the JSON schema automatically.
    - Extracts form_id, version, canonical_size from the YAML.
    - Saves file to configs/templates/ and creates DB record.
    - Scalable: new form types need no code changes.
    """
    if not config_file.filename or not config_file.filename.endswith((".yaml", ".yml")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Config file must be a .yaml or .yml file",
        )

    yaml_bytes = await config_file.read()

    # Validate YAML against schema
    try:
        config = validate_template_yaml(yaml_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid template config: {exc}",
        )

    form_id = config.get("form_id", "").lower()
    version = str(config.get("version", "1.0"))
    canonical = config.get("canonical_size", {})

    if not form_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Config must contain a 'form_id' field",
        )

    # Check duplicate
    existing = (
        await db.execute(select(FormTemplate).where(FormTemplate.form_id == form_id))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template with form_id='{form_id}' already exists. Deactivate it first.",
        )

    # Persist YAML to disk
    config_path = save_template_config(form_id, version, yaml_bytes)

    template = FormTemplate(
        form_id          = form_id,
        name             = name,
        version          = version,
        config_path      = config_path,
        canonical_width  = canonical.get("width", 1654),
        canonical_height = canonical.get("height", 2339),
        is_active        = True,
        created_by       = current_user.id,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


@router.get(
    "/templates",
    response_model=list[FormTemplateResponse],
    summary="List all active form templates",
)
async def list_templates(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    templates = (
        await db.execute(
            select(FormTemplate)
            .where(FormTemplate.is_active == True)  # noqa: E712
            .order_by(FormTemplate.created_at.desc())
        )
    ).scalars().all()
    return list(templates)


# ═══════════════════════════════════════════════════════════════════════════════
# FORM endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "",
    response_model=FormCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a form image — triggers async pipeline",
)
async def submit_form(
    background_tasks: BackgroundTasks,
    form_id: str = Form(..., description="Form type, e.g. 'ct01'"),
    image: UploadFile = File(..., description="Scanned or photographed form image"),
    org_id: UUID = Form(..., description="Ward (phường) the form is submitted to"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a form image and start the extraction pipeline in the background.
    The citizen must pick a valid ward (`org_id`); the form is routed there for review.
    Pipeline: align → ROI extraction → OCR → validate → store result.
    Poll GET /form/{id} to check status and retrieve results.
    """
    # Validate image extension
    ext = get_file_extension(image.filename or "")
    if ext not in _ALLOWED_IMAGE_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type '.{ext}'. Allowed: {', '.join(sorted(_ALLOWED_IMAGE_EXTS))}",
        )

    # Validate the ward exists
    ward = await db.get(Organization, org_id)
    if not ward:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward (org_id) not found")

    # Look up active template
    template = await _get_active_template(form_id.lower(), db)

    # Save uploaded image
    stored_filename, file_path, file_size = await save_upload(image)

    # Create Form record + initial history row
    form = FormModel(
        org_id            = org_id,
        created_by        = current_user.id,
        template_id       = template.id,
        form_id           = template.form_id,
        original_filename = image.filename or stored_filename,
        file_path         = file_path,
        file_size         = file_size,
        status            = FormStatus.submitted,
    )
    db.add(form)
    await db.flush()
    db.add(
        FormStatusHistory(
            form_id=form.id,
            from_status=None,
            to_status=FormStatus.submitted,
            actor_user_id=current_user.id,
            note="Submitted by citizen",
        )
    )
    await db.flush()
    await db.refresh(form)

    background_tasks.add_task(
        _process_form_bg, form.id, file_path, template.config_path
    )

    return FormCreateResponse(
        form_id_db=form.id,
        status=FormStatus.submitted,
        message="Form submitted. Extraction pipeline started. Poll GET /form/{id} for results.",
    )


@router.get(
    "",
    response_model=FormList,
    summary="List submitted forms",
)
async def list_forms(
    page: int = 1,
    page_size: int = 20,
    form_id_filter: str | None = None,
    status_filter: FormStatus | None = None,
    org_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns paginated list of forms, scoped by role:
    - Citizen (no ward membership): only their own submissions.
    - Ward officer/admin: forms submitted to any of their wards.
    - Super_admin: all forms.
    """
    page      = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query       = select(FormModel)
    count_query = select(func.count()).select_from(FormModel)

    # Role-based scoping
    if not current_user.is_superuser:
        ward_ids = await get_user_ward_ids(current_user, db)
        if ward_ids:
            # Ward staff: forms in their ward(s). Also include their own submissions.
            scope = FormModel.org_id.in_(ward_ids) | (FormModel.created_by == current_user.id)
        else:
            # Citizen: only own submissions.
            scope = FormModel.created_by == current_user.id
        query       = query.where(scope)
        count_query = count_query.where(scope)

    if form_id_filter:
        query       = query.where(FormModel.form_id == form_id_filter.lower())
        count_query = count_query.where(FormModel.form_id == form_id_filter.lower())
    if status_filter:
        query       = query.where(FormModel.status == status_filter)
        count_query = count_query.where(FormModel.status == status_filter)
    if org_id:
        query       = query.where(FormModel.org_id == org_id)
        count_query = count_query.where(FormModel.org_id == org_id)

    total = (await db.execute(count_query)).scalar_one()
    forms = (
        await db.execute(
            query.order_by(FormModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return FormList(total=total, page=page, page_size=page_size, items=list(forms))


@router.get(
    "/{form_db_id}",
    response_model=FormDetailResponse,
    summary="Get full form detail including extracted & validated fields",
)
async def get_form(
    form_db_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the full result of a submitted form:
    - alignment metadata (method, quality tier, inliers)
    - extracted_fields: raw OCR output per field (text, confidence, bbox, …)
    - validated_fields: cleaned values after field-specific validators
    """
    form = await _get_form_or_404(form_db_id, db)
    await assert_form_ward_access(form, current_user, db)
    return form


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEW FLOW endpoints (cán bộ phường / super_admin)
# ═══════════════════════════════════════════════════════════════════════════════

async def _get_form_for_review(form_db_id: UUID, current_user: User, db: AsyncSession) -> FormModel:
    """Lock the form row and assert the caller is staff of its ward (or super_admin)."""
    form = await db.get(FormModel, form_db_id, with_for_update=True)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    if not current_user.is_superuser:
        if form.org_id is None or not await get_user_membership(form.org_id, current_user, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return form


def _assert_transition(form: FormModel, to_status: FormStatus) -> None:
    allowed = REVIEW_PREDECESSORS.get(to_status.value, set())
    if form.status.value not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot move form from '{form.status.value}' to '{to_status.value}'",
        )


@router.post("/{form_db_id}/review", response_model=FormDetailResponse,
             summary="[Ward staff] Start reviewing a form")
async def start_review(
    form_db_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    form = await _get_form_for_review(form_db_id, current_user, db)
    _assert_transition(form, FormStatus.under_review)
    record_status_change(db, form, FormStatus.under_review, actor_user_id=current_user.id)
    await db.flush()
    await db.refresh(form)
    return form


@router.post("/{form_db_id}/decision", response_model=FormDetailResponse,
             summary="[Ward staff] Approve or reject a form")
async def decide_form(
    form_db_id: UUID,
    body: DecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target = FormStatus.approved if body.decision == "approved" else FormStatus.rejected
    form = await _get_form_for_review(form_db_id, current_user, db)
    _assert_transition(form, target)
    form.reviewed_by = current_user.id
    form.reviewed_at = datetime.now(timezone.utc)
    form.review_note = body.note
    record_status_change(db, form, target, actor_user_id=current_user.id, note=body.note)
    await db.flush()
    await db.refresh(form)
    return form


@router.post("/{form_db_id}/result", response_model=FormDetailResponse,
             summary="[Ward staff] Return the result to the citizen")
async def return_result(
    form_db_id: UUID,
    body: ResultRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    form = await _get_form_for_review(form_db_id, current_user, db)
    _assert_transition(form, FormStatus.returned)
    form.result_message   = body.result_message
    form.result_file_path = body.result_file_path
    record_status_change(db, form, FormStatus.returned, actor_user_id=current_user.id)
    await db.flush()
    await db.refresh(form)
    return form


@router.get("/{form_db_id}/history", response_model=list[FormStatusHistoryItem],
            summary="Status history of a form (lịch sử của 1 form)")
async def get_form_history(
    form_db_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    form = await _get_form_or_404(form_db_id, db)
    await assert_form_ward_access(form, current_user, db)
    rows = (
        await db.execute(
            select(FormStatusHistory)
            .where(FormStatusHistory.form_id == form_db_id)
            .order_by(FormStatusHistory.created_at)
        )
    ).scalars().all()
    return list(rows)
