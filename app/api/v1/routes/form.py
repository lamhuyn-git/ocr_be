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
from uuid import UUID

import yaml
from fastapi import (
    APIRouter, BackgroundTasks, Depends, File,
    Form, HTTPException, UploadFile, status,
)
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_current_superuser
from app.database import get_db
from app.models.form import Form as FormModel, FormStatus, FormTemplate
from app.models.user import User
from app.schemas.form import (
    FormCreateResponse, FormDetailResponse,
    FormList, FormResponse, FormTemplateResponse,
)
from app.services.form_service import (
    run_form_pipeline, save_template_config, validate_template_yaml,
)
from app.utils.file_utils import save_upload, delete_file, get_file_extension

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/form", tags=["Form"])

_ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "bmp", "tiff", "webp"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assert_owns_or_admin(form: FormModel, user: User) -> None:
    if not user.is_superuser and form.created_by != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


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
    """Run pipeline in background; update DB when done."""
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        form = await db.get(FormModel, form_db_id)
        if not form:
            return

        form.status = FormStatus.processing
        await db.commit()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, run_form_pipeline, image_path, config_path
            )
            form.extracted_fields   = result["extracted_fields"]
            form.validated_fields   = result["validated_fields"]
            form.confidence_score   = result["confidence_score"]
            form.alignment_method   = result["alignment_method"]
            form.alignment_quality  = result["alignment_quality"]
            form.alignment_meta     = result["alignment_meta"]
            form.processing_time_ms = result["processing_time_ms"]
            form.status             = FormStatus.completed
        except Exception as exc:
            logger.exception("Form pipeline failed for %s", form_db_id)
            form.status        = FormStatus.failed
            form.error_message = str(exc)

        await db.commit()


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
    org_id: UUID | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a form image and start the extraction pipeline in the background.
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

    # Look up active template
    template = await _get_active_template(form_id.lower(), db)

    # Save uploaded image
    stored_filename, file_path, file_size = await save_upload(image)

    # Create Form record
    form = FormModel(
        org_id            = org_id,
        created_by        = current_user.id,
        template_id       = template.id,
        form_id           = template.form_id,
        original_filename = image.filename or stored_filename,
        file_path         = file_path,
        file_size         = file_size,
        status            = FormStatus.pending,
    )
    db.add(form)
    await db.flush()
    await db.refresh(form)

    background_tasks.add_task(
        _process_form_bg, form.id, file_path, template.config_path
    )

    return FormCreateResponse(
        form_id_db=form.id,
        status=FormStatus.pending,
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
    Returns paginated list of forms.
    - Regular users see only their own submissions.
    - Superusers see all.
    """
    page      = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query       = select(FormModel)
    count_query = select(func.count()).select_from(FormModel)

    # Scope to current user unless superuser
    if not current_user.is_superuser:
        query       = query.where(FormModel.created_by == current_user.id)
        count_query = count_query.where(FormModel.created_by == current_user.id)

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
    _assert_owns_or_admin(form, current_user)
    return form
