from __future__ import annotations
import logging
from datetime import date, timedelta
from uuid import UUID
from fastapi import ( APIRouter, BackgroundTasks, Depends, HTTPException, Query, status,)
from sqlalchemy import select, delete as sa_delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import ( get_current_user, get_user_ward_ids, get_current_staff, assert_form_ward_access,)
from app.database import get_db

from app.models.form import ( FormType, Form as FormModel, TamtruForm, Evidence, FormResult, FormStatus, ResultConfirm, FormResultStatus, DisplayStatus)
from app.models.organization import Organization
from app.models.user import User

from app.schemas.form import ( FormCreateResponse, FormResponse, FormDetailResponse, FormCreate, FormDraftCreate, UserFormListItem, UserFormListResponse, UserFormCounts, UserFormDetailResponse, AdminSaveChangeRequest, )
from app.schemas.form.evidence import FormEvidencesDetail
from app.schemas.form.form_result import FormResultDetailResponse, ResultHistoryItem
from app.schemas.form.form_type import FormTypeResponse
from app.schemas.form.tamtru_form import TamtruFormDetailResponse
from app.schemas.organization import OrgDetailResponse
from app.schemas.user import UserResponse

from app.services import form_workflow as wf
from app.services import s3_service
from app.services.notification_service import notify_form_submitted
from app.utils.file_utils import get_file_extension


logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/form", tags=["Form"])


_ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "bmp", "tiff", "webp"}
# Gom nhóm stt nội bộ 
_DRAFT_STATUS = FormStatus.draft
_RETURN_STATUSES = (FormStatus.returned,)


async def _upsert_tamtru(form_id: UUID, spec, db: AsyncSession) -> None:
    existing = (await db.execute(select(TamtruForm).where(TamtruForm.form_id == form_id))).scalar_one_or_none()
    target = existing or TamtruForm(form_id=form_id)
    target.case = spec.case
    target.type = spec.type
    target.submit_type = spec.submit_type
    target.location_register = spec.location_register
    target.registered_user_cccd = spec.registered_user_cccd
    target.registered_user_name = spec.registered_user_name
    target.registered_user_birth = spec.registered_user_birth
    target.registered_user_gender = spec.registered_user_gender
    target.registered_user_phone = spec.registered_user_phone
    target.registered_user_mail = spec.registered_user_mail
    target.register_content = spec.register_content
    target.residence_until = spec.residence_until
    if existing is None:
        db.add(target)


async def _finalize_and_dispatch(registered_user_id: UUID, form: FormModel, evidence_paths: list[str], db: AsyncSession, background_tasks: BackgroundTasks,) -> None:
    # Kiểm tra có ảnh
    if not evidence_paths:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one evidence is required")
    # Lọc path ảnh CT01
    ct01_path = next((p for p in evidence_paths if "CT01" in p.upper()), None)
    if ct01_path is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing CT01 image (evidence path must contain 'CT01')")
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
    # Chạy ngầm workflow trích xuất
    background_tasks.add_task(wf.process_form_bg, form.id, ct01_path, template.config_path)


def _presign_path(path_url: str | None) -> str | None:
    if not path_url:
        return None
    try:
        key = s3_service.key_from_path_url(path_url)
        return s3_service.generate_presigned_get(key)
    except Exception:
        return path_url  # fallback: trả path gốc nếu presign thất bại


async def _build_form_detail(form: FormModel, db: AsyncSession) -> FormDetailResponse:
    org       = await db.get(Organization, form.org_id) if form.org_id else None
    form_type = await db.get(FormType, form.form_type_id) if form.form_type_id else None
    tamtru    = (await db.execute(select(TamtruForm).where(TamtruForm.form_id == form.id))).scalar_one_or_none()
    evidences = (await db.execute(select(Evidence).where(Evidence.form_id == form.id))).scalars().all()
    results   = (await db.execute(select(FormResult).where(FormResult.form_id == form.id).order_by(FormResult.label))).scalars().all()

    # Lấy tất cả confirm_results của mỗi field để làm result_history.
    result_ids = [r.id for r in results]
    confirms_by_field: dict[UUID, list[ResultConfirm]] = {}
    if result_ids:
        confirms = (await db.execute(
            select(ResultConfirm)
            .where(ResultConfirm.checkpoint_id.in_(result_ids))
            .order_by(ResultConfirm.created_at)
        )).scalars().all()
        for c in confirms:
            confirms_by_field.setdefault(c.checkpoint_id, []).append(c)

    # Lấy thông tin cán bộ đã confirm cho result_history.
    confirmer_ids = {
        c.confirmed_by
        for lst in confirms_by_field.values() for c in lst if c.confirmed_by
    }
    user_by_id: dict[UUID, UserResponse] = {}
    if confirmer_ids:
        users = (await db.execute(
            select(User).where(User.id.in_(confirmer_ids))
        )).scalars().all()
        user_by_id = {u.id: UserResponse.model_validate(u) for u in users}

    validated_results = []
    for r in results:
        item = FormResultDetailResponse.model_validate(r)
        field_confirms = confirms_by_field.get(r.id, [])
        # Giá trị field = OCR thô, fallback gợi ý CSDL.
        field_value = r.raw_value or r.suggested_value
        # result_history = bản gốc (system) + từng lần confirm.
        history = [ResultHistoryItem(
            source="system", status=r.status, value=field_value, created_at=r.created_at,
        )]
        for c in field_confirms:
            history.append(ResultHistoryItem(
                source="confirm",
                status=FormResultStatus(c.final_status.value),
                value=field_value,
                confirmed_by=user_by_id.get(c.confirmed_by),
                created_at=c.created_at,
            ))
        item.result_history = history
        # Top-level vẫn phản ánh trạng thái mới nhất (confirm cuối nếu có).
        if field_confirms:
            last = field_confirms[-1]
            item.status = FormResultStatus(last.final_status.value)
            item.confirmed_by = last.confirmed_by
            confirmer = user_by_id.get(last.confirmed_by)
            item.confirmed_by_email = confirmer.email if confirmer else None
        validated_results.append(item)

    # Lấy evidences group
    ev_detail = FormEvidencesDetail()
    for ev in evidences:
        upper = (ev.path_url or "").upper()
        if "CT01" in upper:
            ev_detail.warped_img = _presign_path(ev.warped_img or ev.path_url)
        elif "RESIDENCE_PROOF" in upper:
            ev_detail.residence_proof = _presign_path(ev.path_url)

    return FormDetailResponse(
        id=form.id,
        form_type_id=form.form_type_id,
        org_id=form.org_id,
        submit_by=form.submit_by,
        status=form.status,
        notification_on=form.notification_on,
        review_note=form.review_note,
        is_gate_rejected=form.is_gate_rejected,
        created_at=form.created_at,
        updated_at=form.updated_at,
        ogr_detailliated=OrgDetailResponse.model_validate(org) if org else None,
        form_type_detail=FormTypeResponse.model_validate(form_type) if form_type else None,
        sumited_content=TamtruFormDetailResponse.model_validate(tamtru) if tamtru else None,
        evidences=ev_detail,
        validated_results=validated_results,
    )


async def _build_user_form_detail(form: FormModel, db: AsyncSession) -> UserFormDetailResponse:
    org       = await db.get(Organization, form.org_id) if form.org_id else None
    form_type = await db.get(FormType, form.form_type_id) if form.form_type_id else None
    tamtru    = (await db.execute(select(TamtruForm).where(TamtruForm.form_id == form.id))).scalar_one_or_none()
    evidences = (await db.execute(select(Evidence).where(Evidence.form_id == form.id))).scalars().all()

    # Trả ảnh GỐC user upload (path_url), không dùng warped_img đã nắn của pipeline duyệt.
    ev_detail = FormEvidencesDetail()
    for ev in evidences:
        upper = (ev.path_url or "").upper()
        if "CT01" in upper:
            ev_detail.warped_img = _presign_path(ev.path_url)
        elif "RESIDENCE_PROOF" in upper:
            ev_detail.residence_proof = _presign_path(ev.path_url)

    return UserFormDetailResponse(
        id=form.id,
        form_type_id=form.form_type_id,
        org_id=form.org_id,
        status=_display_status(form.status),
        notification_on=form.notification_on,
        created_at=form.created_at,
        updated_at=form.updated_at,
        ogr_detailliated=OrgDetailResponse.model_validate(org) if org else None,
        form_type_detail=FormTypeResponse.model_validate(form_type) if form_type else None,
        sumited_content=TamtruFormDetailResponse.model_validate(tamtru) if tamtru else None,
        evidences=ev_detail,
    )


def _display_status(status: FormStatus) -> DisplayStatus:
    if status == _DRAFT_STATUS:
        return DisplayStatus.draft
    if status in _RETURN_STATUSES:
        return DisplayStatus.returned
    return DisplayStatus.submitted  # _UNDER_REVIEW_STATUSES  


@router.get("/list", response_model=list[FormResponse], summary="List submitted forms filtered by type and/or organization")
async def list_forms_by_type(
    background_tasks: BackgroundTasks,
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

    await wf.mark_overdue_forms(db, settings.overdue_days)
    await wf.requeue_stale_processing(db, background_tasks, settings.stale_processing_minutes)

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
    await _finalize_and_dispatch(formCreate.form_spec.registered_user_cccd, form, [ev.path_url for ev in formCreate.evidences], db, background_tasks)
    await db.flush()
    await db.refresh(form)
    background_tasks.add_task(notify_form_submitted, form.id) 
    return FormCreateResponse(form_id_db=form.id, status=form.status)


@router.get("/detail", response_model=None, summary="Get detail form by its ID")
async def get_detail_forms_by_id(form_id: UUID, current_user: User = Depends(get_current_staff), db: AsyncSession = Depends(get_db)):
    form = await db.get(FormModel, form_id)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    await assert_form_ward_access(form, current_user, db)

    # Nếu stt là submitted/processing thì chỉ trả status
    if form.status in (FormStatus.submitted, FormStatus.processing):
        return FormCreateResponse(form_id_db=form.id, status=form.status)

    # Khi mà form có stt là under_review và do cán bộ KHÁC đang giữ thì chỉ trả status
    if (form.status == FormStatus.under_review and form.reviewer_id not in (None, current_user.id)):
        return FormCreateResponse(form_id_db=form.id, status=form.status)

    if form.status != FormStatus.under_review or form.reviewer_id != current_user.id:
        form.status = FormStatus.under_review
        form.reviewer_id = current_user.id
        await db.commit()
        await db.refresh(form)
    return await _build_form_detail(form, db)


@router.post("/reextract", response_model=FormCreateResponse, status_code=status.HTTP_202_ACCEPTED, summary="Kích hoạt lại trích xuất OCR cho một form")
async def reextract_form(
    background_tasks: BackgroundTasks,
    form_id: UUID,
    current_user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    form = await db.get(FormModel, form_id)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    await assert_form_ward_access(form, current_user, db)
    if form.status not in wf.MANUAL_REEXTRACT_STATES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Không thể trích xuất lại khi form ở trạng thái '{form.status.value}'",
        )
    ok = await wf.dispatch_reextract(form, db, background_tasks)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Thiếu ảnh CT01 hoặc template chưa được cấu hình",
        )
    await db.commit()
    await db.refresh(form)
    return FormCreateResponse(form_id_db=form.id, status=form.status)


@router.post("/save_change", status_code=status.HTTP_200_OK, summary="Lưu draft duyệt hồ sơ (admin)")
async def admin_save_change(
    body: AdminSaveChangeRequest,
    current_user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    form = await db.get(FormModel, body.form_id)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    
    await assert_form_ward_access(form, current_user, db)

    has_change = bool(body.updated_fields)
    if has_change:
        for item in body.updated_fields:
            result = await db.get(FormResult, item.id)
            if not result or result.form_id != body.form_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"FormResult {item.id} not found in form {body.form_id}")
            db.add(ResultConfirm(
                checkpoint_id=item.id,
                confirmed_by=body.confirmed_by,
                final_status=item.status,
            ))

    if body.from_status == FormStatus.gate_rejected:
        form.status = FormStatus.reviewed
    else:
        form.status = FormStatus.reviewed if has_change else body.from_status

    # Cán bộ thoát khỏi trang soát → nhả lock để người khác vào xử lý được.
    form.reviewer_id = None

    await db.commit()
    return {"form_id": body.form_id, "status": form.status}


@router.post("/draft", response_model=FormCreateResponse, status_code=status.HTTP_200_OK, summary="Lưu draft hồ sơ của citizen")
async def save_as_draft(
    body: FormDraftCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    form = FormModel(
        form_type_id=body.form_type_id,
        org_id=body.org_id,
        submit_by=current_user.id,
        notification_on=body.notification_on,
        status=FormStatus.draft,
    )
    db.add(form)
    await db.flush()

    # Tạo Evidence (nếu có)
    if body.evidences:
        for path_url in (ev.path_url for ev in body.evidences):
            db.add(Evidence(form_id=form.id, path_url=path_url))

    # Draft: giữ lại dữ liệu đã khai kể cả khi chưa chọn thủ tục (form_type_id null).
    if body.form_spec:
        await _upsert_tamtru(form.id, body.form_spec, db)

    await db.flush()
    await db.refresh(form)
    return FormCreateResponse(form_id_db=form.id, status=form.status)


@router.get("/user-list", response_model=UserFormListResponse, summary="List a citizen's own forms (paginated)",)
async def list_user_forms(
    user_id: UUID,
    group: str | None = Query(default=None),
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    if not current_user.is_superuser and user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Forbidden")

    # Count theo status của DB
    status_rows = (
        await db.execute(
            select(FormModel.status, func.count())
            .where(FormModel.submit_by == user_id)
            .group_by(FormModel.status)
        )
    ).all()

    # Gom về 3 nhóm hiển thị cho FE
    display_counts = {
        DisplayStatus.draft: 0,
        DisplayStatus.submitted: 0,
        DisplayStatus.returned: 0,
    }

    for db_status, count in status_rows:
        display_counts[_display_status(db_status)] += count

    counts = UserFormCounts(
        all=sum(display_counts.values()),
        draft=display_counts[DisplayStatus.draft],
        submitted=display_counts[DisplayStatus.submitted],
        returned=display_counts[DisplayStatus.returned],
    )
    query = (
        select(
            FormModel,
            FormType.type_name,
            TamtruForm.location_register,
        )
        .outerjoin(FormType, FormType.id == FormModel.form_type_id)
        .outerjoin(TamtruForm, TamtruForm.form_id == FormModel.id)
        .where(FormModel.submit_by == user_id)
    )

    if group == "draft":
        query = query.where(FormModel.status == FormStatus.draft)

    elif group == "submitted":
        query = query.where(FormModel.status != FormStatus.draft)

    total = (
        await db.execute(
            select(func.count()).select_from(query.subquery())
        )
    ).scalar_one()

    rows = (
        await db.execute(
            query.order_by(FormModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = [
        UserFormListItem(
            id=form.id,
            code=str(form.id),
            status=_display_status(form.status),
            form_type_name=type_name,
            location=location,
            created_at=form.created_at,
            completed_at=(
                form.updated_at
                if form.status == FormStatus.returned
                else None
            ),
            reject_reason=form.review_note,
            notify_method=form.notification_on,
        )
        for form, type_name, location in rows
    ]

    return UserFormListResponse(
        items=items,
        total=total,
        counts=counts,
    )


@router.get("/user/detail", response_model=UserFormDetailResponse, summary="Citizen xem chi tiết hồ sơ của chính mình")
async def get_user_form_detail(
    form_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    form = await db.get(FormModel, form_id)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    # Chỉ chủ hồ sơ (hoặc superuser) được xem.
    if not current_user.is_superuser and form.submit_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return await _build_user_form_detail(form, db)