from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status,
)
from pydantic import ValidationError
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_current_user, get_current_superuser, assert_form_ward_access, get_user_ward_ids, get_current_staff,
)
from app.database import get_db
from app.models.form import (
    FormType, FormTemplate, Form as FormModel, DetailForm,
    HistoryContent, FormStatus, FormStatusHistory,

)
from app.models.organization import Organization
from app.models.user import User
from app.schemas.form import (
    ContentUpdateRequest, DecisionRequest, FormCreateResponse, FormDetailResponse,
    FormExtractResponse, FormList, FormResponse, FormStatusHistoryItem,
    FormTemplateResponse, FormTypeResponse, HistoryContentItem, ResultRequest, FormCreate
)
from app.services import form_workflow as wf
from app.services.form_service import run_form_pipeline, save_template_config, validate_template_yaml
from app.utils.file_utils import save_upload, delete_file, get_file_extension

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/form", tags=["Form"])

_ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "bmp", "tiff", "webp"}



@router.post("/types", response_model=FormTypeResponse, status_code=status.HTTP_201_CREATED, summary="Create a form type")
async def create_form_type(
    type_name: str = Form(..., description="Mã loại form, vd 'ct01'"),
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    name = type_name.strip().lower()
    if (await db.execute(select(FormType).where(FormType.type_name == name))).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Form type already exists")
    form_type = FormType(type_name=name)
    db.add(form_type)
    await db.flush()
    await db.refresh(form_type)
    return form_type


@router.post("/templates", response_model=FormTemplateResponse, status_code=status.HTTP_201_CREATED, summary="Upload a template version")
async def create_template(
    form_type_id: UUID = Form(..., description="Form type ID this template belongs to"),
    name: str = Form(..., description="Tên template, vd 'Đơn CT-01'"),
    version: str = Form(default="1.0"),
    config_file: UploadFile = File(..., description="YAML config"),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    if not config_file.filename or not config_file.filename.endswith((".yaml", ".yml")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Config must be .yaml/.yml")
    yaml_bytes = await config_file.read()
    try:
        validate_template_yaml(yaml_bytes)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Invalid template config: {exc}")

    config_path = save_template_config(name, version, yaml_bytes)
    actives = (
        await db.execute(
            select(FormTemplate).where(FormTemplate.form_type_id == form_type_id, FormTemplate.is_active == True)  # noqa: E712
        )
    ).scalars().all()
    for t in actives:
        t.is_active = False

    template = FormTemplate(form_type_id=form_type_id, name=name, version=version,
                            config_path=config_path, is_active=True, created_by=current_user.id)
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


@router.get("/types", response_model=list[FormResponse], summary="List submitted forms filtered by type and/or organization")
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

    # Mặc định lấy tất cả; mỗi filter chỉ áp khi có giá trị (bỏ trống → không lọc theo tiêu chí đó).
    query = select(FormModel)

    # Scope theo quyền: superadmin xem mọi phường; staff chỉ xem phường mình là thành viên.
    if not current_user.is_superuser:
        ward_ids = await get_user_ward_ids(current_user, db)
        if not ward_ids:
            return []                                  # staff chưa thuộc phường nào → không thấy gì
        query = query.where(FormModel.org_id.in_(ward_ids))

    if type_id is not None:
        query = query.where(FormModel.form_type_id == type_id)
    if organization_id is not None:
        query = query.where(FormModel.org_id == organization_id)
    if status_filter is not None:
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
    background_tasks: BackgroundTasks,  # chạy việc nền sau khi đã trả response
    payload: str = Form(..., description="Form số người dân nộp (JSON, khớp FormCreate)"),
    image: UploadFile = File(..., description="Ảnh form (bytes)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate phần JSON → nested model
    try:
        body = FormCreate.model_validate_json(payload)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors())

    # Kiểm tra đuôi ảnh
    ext = get_file_extension(image.filename or "")
    if ext not in _ALLOWED_IMAGE_EXTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported image '.{ext}'")

    # Kiểm tra org_id và form_type_id có tồn tại hay không
    if not await db.get(Organization, body.co_quan_thuc_hien.org_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward (org_id) not found")
    if not await db.get(FormType, body.thu_tuc_yeu_cau.form_type_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form type not found")

    # Lấy template active cho form_type_id
    template = await wf.active_template_for_type_id(body.thu_tuc_yeu_cau.form_type_id, db)

    # Lưu ảnh (bytes) → trả về key/path
    stored_filename, file_path, file_size = await save_upload(image, user_id=str(current_user.id))

    # Thêm 1 bản ghi Form
    form = FormModel(
        form_type_id=body.thu_tuc_yeu_cau.form_type_id,
        org_id=body.co_quan_thuc_hien.org_id,
        user_id=current_user.id,
        status=FormStatus.submitted,
        original_filename=image.filename or stored_filename,
        file_path=file_path, file_size=file_size,
    )
    db.add(form)
    await db.flush()

    # DetailForm (origin_content) — lưu cả form số đã validate
    db.add(DetailForm(form_id=form.id, origin_content=body.model_dump(mode="json")))
    # FormStatusHistory (submitted)
    db.add(FormStatusHistory(form_id=form.id, from_status=None, to_status=FormStatus.submitted,
                             actor_user_id=current_user.id, note="Submitted by citizen"))
    await db.flush()
    await db.refresh(form)

    background_tasks.add_task(wf.process_form_bg, form.id, file_path, template.config_path)
    return FormCreateResponse(form_id_db=form.id, status=FormStatus.submitted)


# @router.get("", response_model=FormList, summary="List forms")
# async def list_forms(
#     page: int = 1,
#     page_size: int = 20,
#     status_filter: FormStatus | None = None,
#     org_id: UUID | None = None,
#     current_user: User = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     page = max(page, 1)
#     page_size = min(max(page_size, 1), 100)
#     query = select(FormModel)
#     count_query = select(func.count()).select_from(FormModel)

#     if not current_user.is_superuser:
#         ward_ids = await get_user_ward_ids(current_user, db)
#         scope = (FormModel.org_id.in_(ward_ids) | (FormModel.user_id == current_user.id)) if ward_ids \
#             else (FormModel.user_id == current_user.id)
#         query = query.where(scope)
#         count_query = count_query.where(scope)
#     if status_filter:
#         query = query.where(FormModel.status == status_filter)
#         count_query = count_query.where(FormModel.status == status_filter)
#     if org_id:
#         query = query.where(FormModel.org_id == org_id)
#         count_query = count_query.where(FormModel.org_id == org_id)

#     total = (await db.execute(count_query)).scalar_one()
#     forms = (
#         await db.execute(query.order_by(FormModel.created_at.desc())
#                          .offset((page - 1) * page_size).limit(page_size))
#     ).scalars().all()
#     return FormList(total=total, page=page, page_size=page_size, items=list(forms))


@router.get("/{form_db_id}", response_model=FormDetailResponse, summary="Get form detail by form ID")
async def get_form(form_db_id: UUID, current_user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_db)):
    form = await wf.get_form_or_404(form_db_id, db)
    await assert_form_ward_access(form, current_user, db)
    return await wf.build_detail_response(form, db)


@router.get("/{form_db_id}/history", response_model=list[FormStatusHistoryItem], summary="Status history")
async def get_form_history(form_db_id: UUID, current_user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    form = await wf.get_form_or_404(form_db_id, db)
    await assert_form_ward_access(form, current_user, db)
    rows = (
        await db.execute(select(FormStatusHistory).where(FormStatusHistory.form_id == form_db_id)
                         .order_by(FormStatusHistory.created_at))
    ).scalars().all()
    return list(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEW FLOW (ward staff / super_admin)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/{form_db_id}/review", response_model=FormDetailResponse, summary="[Ward staff] Start review")
async def start_review(form_db_id: UUID, current_user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    form = await wf.get_form_for_review(form_db_id, current_user, db)
    wf.assert_transition(form, FormStatus.under_review)
    wf.record_status_change(db, form, FormStatus.under_review, current_user.id)
    await db.flush()
    return await wf.build_detail_response(form, db)


@router.post("/{form_db_id}/decision", response_model=FormDetailResponse, summary="[Ward staff] Approve/reject")
async def decide_form(form_db_id: UUID, body: DecisionRequest,
                      current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    target = FormStatus.approved if body.decision == "approved" else FormStatus.rejected
    form = await wf.get_form_for_review(form_db_id, current_user, db)
    wf.assert_transition(form, target)
    form.reviewed_by = current_user.id
    form.reviewed_at = datetime.now(timezone.utc)
    form.review_note = body.note
    wf.record_status_change(db, form, target, current_user.id, body.note)
    await db.flush()
    return await wf.build_detail_response(form, db)


@router.post("/{form_db_id}/result", response_model=FormDetailResponse, summary="[Ward staff] Return result")
async def return_result(form_db_id: UUID, body: ResultRequest,
                        current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    form = await wf.get_form_for_review(form_db_id, current_user, db)
    wf.assert_transition(form, FormStatus.returned)
    form.result_message = body.result_message
    form.result_file_path = body.result_file_path
    wf.record_status_change(db, form, FormStatus.returned, current_user.id)
    await db.flush()
    return await wf.build_detail_response(form, db)


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACTED-CONTENT EDIT + HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

@router.put("/{form_db_id}/content", response_model=FormDetailResponse,
            summary="[Ward staff] Edit latest extracted content (records a history version)")
async def update_extracted_content(form_db_id: UUID, body: ContentUpdateRequest,
                                   current_user: User = Depends(get_current_user),
                                   db: AsyncSession = Depends(get_db)):
    form = await wf.get_form_for_review(form_db_id, current_user, db)
    latest = await wf.latest_extracted(form_db_id, db)
    if not latest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No extracted result to edit")
    db.add(HistoryContent(extracted_result_id=latest.id, new_content=body.new_content,
                          changed_by=current_user.id))
    latest.content = body.new_content
    await db.flush()
    return await wf.build_detail_response(form, db)


@router.get("/{form_db_id}/content-history", response_model=list[HistoryContentItem],
            summary="Edit history of the latest extracted result")
async def get_content_history(form_db_id: UUID, current_user: User = Depends(get_current_user),
                              db: AsyncSession = Depends(get_db)):
    form = await wf.get_form_or_404(form_db_id, db)
    await assert_form_ward_access(form, current_user, db)
    latest = await wf.latest_extracted(form_db_id, db)
    if not latest:
        return []
    rows = (
        await db.execute(select(HistoryContent).where(HistoryContent.extracted_result_id == latest.id)
                         .order_by(HistoryContent.changed_at))
    ).scalars().all()
    return list(rows)
