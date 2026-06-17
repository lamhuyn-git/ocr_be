from __future__ import annotations

import logging
from datetime import date, timedelta
from uuid import UUID

from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException, Query, status,
)
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import (
    get_current_user, get_current_superuser, get_user_ward_ids, get_current_staff,
    assert_form_ward_access,
)
from app.database import get_db
from app.models.form import (
    FormType, Form as FormModel, TamtruForm, Evidence, FormResult, FormStatus,
)
from app.models.organization import Organization
from app.models.user import User
from app.schemas.form import (
    FormCreateResponse, FormResponse, FormDetailResponse,
    FormCreate, FormDraftCreate, FormDraftUpdate, FormTransitionRequest,
    FormResultConfirmRequest, FormResultResponse,
)
from app.services import form_workflow as wf
from app.utils.file_utils import get_file_extension

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/form", tags=["Form"])

_ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "bmp", "tiff", "webp"}


@router.get("/list", response_model=list[FormResponse], summary="List submitted forms filtered by type and/or organization")
async def list_forms_by_type(
    type_id: UUID | None = None,
    organization_id: UUID | None = None,
    status_filter: FormStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None, description="Lọc các form được nộp từ ngày này"),
    date_to: date | None = Query(default=None, description="Lọc các form được nộp đến hết ngày này"),
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    # Lazy maintenance: đánh overdue hồ sơ quá hạn trước khi trả danh sách (chưa có cron).
    await wf.mark_overdue_forms(db, settings.overdue_days)

    query = select(FormModel)

    # Scope theo quyền: superadmin xem mọi phường; staff chỉ xem phường mình là thành viên.
    if not current_user.is_superuser:
        ward_ids = await get_user_ward_ids(current_user, db)
        if not ward_ids:
            return []
        query = query.where(FormModel.org_id.in_(ward_ids))

    if type_id is not None:
        query = query.where(FormModel.form_type_id == type_id)
    if organization_id is not None:
        query = query.where(FormModel.org_id == organization_id)
    # Không list draft
    query = query.where(FormModel.status != FormStatus.draft)

    if status_filter is not None and status_filter != FormStatus.draft:
        query = query.where(FormModel.status == status_filter)
    if date_from is not None:
        query = query.where(FormModel.created_at >= date_from)
    if date_to is not None:
        query = query.where(FormModel.created_at < date_to + timedelta(days=1))

    query = query.order_by(FormModel.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()
    return list(rows)


async def _upsert_tamtru(form_id: UUID, spec, db: AsyncSession) -> None:
    existing = (await db.execute(select(TamtruForm).where(TamtruForm.form_id == form_id))).scalar_one_or_none()
    target = existing or TamtruForm(form_id=form_id)
    target.case = spec.case
    target.type = spec.type
    target.submit_type = spec.submit_type
    target.location_register = spec.location_register
    target.registered_user_id = spec.registered_user_id
    target.registered_user_name = spec.registered_user_name
    target.registered_user_birth = spec.registered_user_birth
    target.registered_user_gender = spec.registered_user_gender
    target.registered_user_phone = spec.registered_user_phone
    target.registered_user_mail = spec.registered_user_mail
    target.register_content = spec.register_content
    if existing is None:
        db.add(target)


async def _finalize_and_dispatch(
    form: FormModel, evidence_paths: list[str], db: AsyncSession, background_tasks: BackgroundTasks,
) -> None:
    # Kiểm tra có ảnh
    if not evidence_paths:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one evidence is required")
    # Lọc path ảnh CT01
    ct01_path = next((p for p in evidence_paths if "CT01" in p.upper()), None)
    if ct01_path is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Missing CT01 image (evidence path must contain 'CT01')")
    # Kiểm tra đuôi ảnh hợp lệ
    for path_url in evidence_paths:
        ext = get_file_extension(path_url)
        if ext not in _ALLOWED_IMAGE_EXTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported image '.{ext}'")
    # Kiểm tra org_id + form_type_id tồn tại
    if form.org_id is None or not await db.get(Organization, form.org_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward (org_id) not found")
    if form.form_type_id is None or not await db.get(FormType, form.form_type_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form type not found")
    # Resolve template active (config_path để chạy pipeline)
    template = await wf.active_template_for_type_id(form.form_type_id, db)

    form.status = FormStatus.submitted
    # Chạy ngầm workflow trích xuất → processing → form_result → extracted
    background_tasks.add_task(wf.process_form_bg, form.id, ct01_path, template.config_path)


@router.post("", response_model=FormCreateResponse, status_code=status.HTTP_202_ACCEPTED, summary="Submit a form")
async def submit_form(
    background_tasks: BackgroundTasks,
    formCreate: FormCreate,
    db: AsyncSession = Depends(get_db),
):
    # Tạo Form
    form = FormModel(
        form_type_id=formCreate.form_type_id,
        org_id=formCreate.org_id,
        submit_by=formCreate.submit_by,
        notification_on=formCreate.notification_on,
        status=FormStatus.submitted,
    )
    db.add(form)
    await db.flush()

    # Tạo Evidence (file đính kèm)
    for path_url in (ev.path_url for ev in formCreate.evidences):
        db.add(Evidence(form_id=form.id, path_url=path_url))

    # Nếu là đơn đăng ký tạm trú thì tạo bảng con TamtruForm
    if str(formCreate.form_type_id) == settings.tamtru_form_type_id:
        await _upsert_tamtru(form.id, formCreate.form_spec, db)

    # Validation đầy đủ + dispatch OCR (set status=submitted)
    await _finalize_and_dispatch(form, [ev.path_url for ev in formCreate.evidences], db, background_tasks)
    await db.flush()
    await db.refresh(form)
    return FormCreateResponse(form_id_db=form.id, status=form.status)


@router.post("/draft", response_model=FormCreateResponse, status_code=status.HTTP_201_CREATED, summary="Save a form as draft")
async def create_draft(
    draft: FormDraftCreate,
    db: AsyncSession = Depends(get_db),
):
    # Lưu nháp — không validate đầy đủ, không chạy OCR
    form = FormModel(
        form_type_id=draft.form_type_id,
        org_id=draft.org_id,
        submit_by=draft.submit_by,
        notification_on=draft.notification_on,
        status=FormStatus.draft,
    )
    db.add(form)
    await db.flush()

    if draft.evidences:
        for path_url in (ev.path_url for ev in draft.evidences):
            db.add(Evidence(form_id=form.id, path_url=path_url))

    if draft.form_spec is not None:
        await _upsert_tamtru(form.id, draft.form_spec, db)

    await db.flush()
    await db.refresh(form)
    return FormCreateResponse(form_id_db=form.id, status=form.status)


@router.patch("/draft/{form_id}", response_model=FormDetailResponse, summary="Update a draft form")
async def update_draft(
    form_id: UUID,
    draft: FormDraftUpdate,
    db: AsyncSession = Depends(get_db),
):
    form = await wf.get_form_or_404(form_id, db)
    if form.status != FormStatus.draft:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Form is not a draft")

    data = draft.model_dump(exclude_unset=True)
    for field in ("org_id", "form_type_id", "notification_on"):
        if field in data:
            setattr(form, field, data[field])

    # evidences gửi lên → replace toàn bộ
    if draft.evidences is not None:
        await db.execute(sa_delete(Evidence).where(Evidence.form_id == form_id))
        for path_url in (ev.path_url for ev in draft.evidences):
            db.add(Evidence(form_id=form_id, path_url=path_url))
    # form_spec gửi lên → upsert tamtru
    if draft.form_spec is not None:
        await _upsert_tamtru(form_id, draft.form_spec, db)

    await db.flush()
    return await _build_form_detail(form, db)


@router.post("/{form_id}/submit", response_model=FormCreateResponse, status_code=status.HTTP_202_ACCEPTED, summary="Submit a draft form")
async def submit_draft(
    form_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    form = await wf.get_form_or_404(form_id, db)
    if form.status != FormStatus.draft:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Form is not a draft")

    evidence_paths = [
        e.path_url for e in
        (await db.execute(select(Evidence).where(Evidence.form_id == form_id))).scalars().all()
    ]
    await _finalize_and_dispatch(form, evidence_paths, db, background_tasks)
    await db.flush()
    await db.refresh(form)
    return FormCreateResponse(form_id_db=form.id, status=form.status)


@router.post("/scan-overdue", summary="Mark forms overdue (>N ngày chưa xử lý)")
async def scan_overdue(
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    count = await wf.mark_overdue_forms(db, settings.overdue_days)
    return {"updated": count}


@router.post("/{form_id}/transition", response_model=FormDetailResponse,
             summary="Kiểm tra viên chuyển trạng thái hồ sơ")
async def transition_form(
    form_id: UUID,
    body: FormTransitionRequest,
    current_user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    # khóa hàng → ngăn 2 cán bộ cùng xử lý 1 hồ sơ
    form = await db.get(FormModel, form_id, with_for_update=True)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    await assert_form_ward_access(form, current_user, db)

    wf.assert_can_transition(form, body.to_status)
    form.status = body.to_status
    if body.note is not None:
        form.review_note = body.note
    await db.flush()
    return await _build_form_detail(form, db)


async def _build_form_detail(form: FormModel, db: AsyncSession) -> FormDetailResponse:
    """Gộp form + tamtru + evidences + results thành FormDetailResponse."""
    await db.refresh(form)
    tamtru = (await db.execute(select(TamtruForm).where(TamtruForm.form_id == form.id))).scalar_one_or_none()
    evidences = (
        await db.execute(select(Evidence).where(Evidence.form_id == form.id).order_by(Evidence.created_at))
    ).scalars().all()
    results = (
        await db.execute(select(FormResult).where(FormResult.form_id == form.id).order_by(FormResult.position))
    ).scalars().all()

    resp = FormDetailResponse.model_validate(form)
    resp.tamtru = tamtru
    resp.evidences = list(evidences)
    resp.results = list(results)
    return resp
