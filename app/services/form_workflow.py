from __future__ import annotations

import asyncio
import logging
import os
from typing import Any
from uuid import UUID

from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select, update as sa_update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.citizen import Citizen
from app.models.form import (Form, FormTemplate, FormResult, FormStatus, Evidence, TamtruForm,)
from app.models.org_address import OrgAddress
from app.services.form_service import run_form_pipeline
from app.services import s3_service
from app.validation import compute_field_statuses
from app.validation import field_rules as FR
from app.validation.text_match import digits_only, norm_distance, street_part
from app.validation.thresholds import LIST_MATCH_DIST_MAX, NAME_MATCH_DIST_MAX, CCCD_OCR_TYPO_MAX
from rapidfuzz.distance import Levenshtein
from app.services.extraction_error_catalog import EXTRACTION_ERROR_CATALOG, ErrorCode

logger = logging.getLogger(__name__)


# Định nghĩa các ràng buộc khi change stt
ALLOWED_TRANSITIONS: dict[FormStatus, set[FormStatus]] = {
    FormStatus.under_review: {FormStatus.extracted},                  # mở hồ sơ để xem xét (khóa)
    FormStatus.reviewed:     {FormStatus.under_review},               # xong bước kiểm tra/lưu
    FormStatus.returned:     {FormStatus.reviewed, FormStatus.under_review},  # trả kết quả (verdict lưu ở temporary_residences)
}

# Draft, Overdue, và Gate-rejected không thể thành overdue. Stt còn lại đều được.
NOT_OVERDUE_STATES: set[FormStatus] = {FormStatus.draft, FormStatus.overdue, FormStatus.gate_rejected}


# Map mã lỗi
_ISSUE_NOTE = {code: err.message for code, err in EXTRACTION_ERROR_CATALOG.items()}


def assert_can_transition(form: Form, to_status: FormStatus) -> None:
    allowed = ALLOWED_TRANSITIONS.get(to_status)
    if allowed is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Status '{to_status.value}' không thể chuyển thủ công")
    if form.status not in allowed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Không thể chuyển từ '{form.status.value}' thành '{to_status.value}'")


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


# Lấy active template
async def active_template_for_type_id(form_type_id: UUID, db: AsyncSession) -> FormTemplate:
    tmpl = (await db.execute(select(FormTemplate).where(FormTemplate.form_type_id == form_type_id, FormTemplate.is_active == True))).scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No active template for form type id '{form_type_id}'")
    return tmpl


# Map pipeline output → form_result rows

def _bbox_to_xywh(bbox: list) -> list[float] | None:
    if not bbox or len(bbox) < 4:
        return None
    x1, y1, x2, y2 = bbox[:4]
    return [float(x1), float(y1), float(x2 - x1), float(y2 - y1)]


def extracted_fields_to_results(form_id: UUID, result: dict[str, Any], verdicts: dict[str, Any] | None = None,) -> list[FormResult]:
    from app.validation.db_adapter import verdict_to_status
    from app.validation.field_comments import comment_for
    fields = result.get("extracted_fields") or {}
    verdicts = verdicts or {}
    rows: list[FormResult] = []
    for label, field in fields.items():
        if isinstance(field, dict):
            raw = field.get("text")
            ocr_text = field.get("text")
            position = _bbox_to_xywh(field.get("bbox"))
        else:
            raw = ocr_text = (str(field) if field is not None else None)
            position = None

        verdict = verdicts.get(label)
        if verdict is not None:
            suggested = verdict.suggestion if verdict.suggestion is not None else ocr_text
            db_value = verdict.db_value  # giá trị CSDL thật (có cả ở field mềm)
            note = comment_for(label, verdict.code) or verdict.reason
            row_status = verdict_to_status(verdict.status)
        else:
            suggested = ocr_text
            db_value = None
            note = None
            row_status = None

        row = FormResult(
            form_id=form_id, 
            position=position, 
            label=label,
            raw_value=raw, 
            suggested_value=suggested, 
            db_value=db_value, 
            note=note,
        )
        if row_status is not None:
            row.status = row_status
        rows.append(row)
    return rows


# Kiểm tra người đăng ký có thông tin đúng với CSDL không
async def check_registered_user(db: AsyncSession, form_id: UUID) -> tuple[list[str], list[str]]:
    tamtru = (await db.execute(select(TamtruForm).where(TamtruForm.form_id == form_id))).scalar_one_or_none()
    if not tamtru:
        return [], []
    
    # Thiếu số định danh khai online
    if not tamtru.registered_user_cccd:
        return [ErrorCode.registered_user_missing], []

    citizen = (await db.execute(
        select(Citizen).where(Citizen.so_dinh_danh == tamtru.registered_user_cccd)
    )).scalar_one_or_none()
    if not citizen:
        return [ErrorCode.registered_user_not_found], []

    hard: list[ErrorCode] = []
    soft: list[ErrorCode] = []
    # Field khi lệch là chặn cổng luôn
    if tamtru.registered_user_name:
        if norm_distance(tamtru.registered_user_name, citizen.ho_chu_dem_va_ten or "") > NAME_MATCH_DIST_MAX:
            hard.append(ErrorCode.registered_user_name)
    if tamtru.registered_user_birth and citizen.ngay_sinh:
        if tamtru.registered_user_birth != citizen.ngay_sinh:
            hard.append(ErrorCode.registered_user_birth)
    if tamtru.registered_user_gender and citizen.gioi_tinh:
        if tamtru.registered_user_gender.lower() != str(citizen.gioi_tinh.value).lower():
            hard.append(ErrorCode.registered_user_gender)
    # Field khi lệch chỉ ghi chú, không chặn
    if tamtru.registered_user_phone and citizen.so_dien_thoai:
        if tamtru.registered_user_phone != citizen.so_dien_thoai:
            soft.append(ErrorCode.registered_user_phone)
    if tamtru.registered_user_mail and citizen.email:
        if tamtru.registered_user_mail.lower() != citizen.email.lower():
            soft.append(ErrorCode.registered_user_mail)
    return hard, soft


# Kiểm tra địa chỉ đăng ký (location_register) có thuộc phường tiếp nhận không
async def check_location_register(db: AsyncSession, form_id: UUID) -> list[str]:
    rows = (await db.execute(
        select(TamtruForm.location_register, OrgAddress.dia_chi)
        .join(Form, Form.id == TamtruForm.form_id)
        .join(OrgAddress, OrgAddress.org_id == Form.org_id)
        .where(TamtruForm.form_id == form_id, OrgAddress.is_active == True)  # noqa: E712
    )).all()

    # Không có cặp nào: form chưa khai địa chỉ, hoặc phường chưa nạp địa chỉ quản lý
    if not rows:
        return []

    location = rows[0][0]
    if not (location or "").strip():
        return []

    # Chỉ so phần "số nhà + tên đường" (bỏ hậu tố phường/thành phố vốn luôn trùng)
    # để fuzzy match không bị loãng. Khớp nếu gần ít nhất 1 dia_chi của phường.
    loc_key = street_part(location)
    best = min(norm_distance(loc_key, street_part(dia_chi)) for _, dia_chi in rows)
    if best > LIST_MATCH_DIST_MAX:
        return [ErrorCode.location_not_in_ward]
    return []


def _ocr_text(result: dict[str, Any], label: str) -> str:
    f = (result.get("extracted_fields") or {}).get(label)
    if isinstance(f, dict):
        return f.get("text") or ""
    return str(f) if f is not None else ""


async def check_same_person(result: dict[str, Any], db: AsyncSession, form_id: UUID) -> tuple[bool, list[ErrorCode]]:
    tamtru = (await db.execute(
        select(TamtruForm).where(TamtruForm.form_id == form_id)
    )).scalar_one_or_none()
    if not tamtru:
        return True, []

    online_cccd = digits_only(tamtru.registered_user_cccd or "")
    ct01_cccd = digits_only(_ocr_text(result, FR.KEY_CCCD_NGUOI_DK))
    ct01_name = _ocr_text(result, "ho_chu_dem_va_ten")
    name_ok = bool(
        tamtru.registered_user_name and ct01_name
        and norm_distance(ct01_name, tamtru.registered_user_name) <= NAME_MATCH_DIST_MAX
    )

    # CCCD trên CT01 đọc đủ 12 số → so trực tiếp.
    if len(ct01_cccd) == 12:
        if online_cccd and ct01_cccd == online_cccd:
            return True, []
        # CCCD lệch ÍT ký tự (nghi OCR nhầm) NHƯNG họ tên khớp → không chặn cổng,
        # chỉ ghi chú để cán bộ tự đối chiếu (tránh false-reject do OCR đọc sai).
        if name_ok and Levenshtein.distance(ct01_cccd, online_cccd) <= CCCD_OCR_TYPO_MAX:
            return True, [ErrorCode.ct01_cccd_minor_name_ok]
        return False, [ErrorCode.ct01_cccd_mismatch]

    # CCCD CT01 không đọc được → fallback so họ tên (yếu, chỉ khi bất khả kháng).
    if name_ok:
        return True, []
    return False, [ErrorCode.ct01_person_unverified]


def _build_review_note(issues: list[str]) -> str:
    return "; ".join(_ISSUE_NOTE.get(i, i) for i in issues)


# Background extraction workflow
async def process_form_bg(form_db_id: UUID, image_path: str, config_path: str) -> None:
    runnable_status = {FormStatus.submitted, FormStatus.processing}
    logger.info("[BG-OCR] START form=%s image=%s config=%s", form_db_id, image_path, config_path)

    # Mở kết nối tới database
    async with AsyncSessionLocal() as db:
        # Lấy form cụ thể theo mã số & giữ riêng hồ sơ này, không cho ai khác sửa cùng lúc
        form = await db.get(Form, form_db_id, with_for_update=True)
        if not form or form.status not in runnable_status:
            logger.warning("[BG-OCR] SKIP form=%s status=%s (không ở trạng thái chạy được)", form_db_id, getattr(form, "status", None))
            await db.rollback()
            return
        form.status = FormStatus.processing
        await db.commit()

    # Kiểm tra các thông tin điền trên form online có hợp lệ hay không (bao gồm registered_user và địa chỉ thuộc phường)
    soft_notes: list[str] = []
    async with AsyncSessionLocal() as db:
        hard, soft = await check_registered_user(db, form_db_id)
        hard += await check_location_register(db, form_db_id)
        if hard:
            logger.warning("[BG-OCR] pre-extract gate fail form=%s hard=%s soft=%s", form_db_id, hard, soft)
            form = await db.get(Form, form_db_id, with_for_update=True)
            if form:
                form.status = FormStatus.gate_rejected
                form.is_gate_rejected = True
                form.review_note = _build_review_note(hard + soft)
                await db.commit()
            return
        soft_notes = soft

    # Bắt đầu trích xuất
    logger.info("[BG-OCR] EXTRACTING form=%s", form_db_id)
    try:
        # Việc nặng đẩy sang luồng riêng
        loop = asyncio.get_running_loop()
        # Tải ảnh từ S3 về một file tạm trên máy.
        local_image = await loop.run_in_executor(None, s3_service.download_to_temp, image_path)
        try:
            result = await loop.run_in_executor(None, run_form_pipeline, local_image, config_path)
        finally:
            await loop.run_in_executor(None, _safe_remove, local_image)
        logger.info("[BG-OCR] pipeline xong form=%s", form_db_id)
    except Exception as exc:
        logger.exception("[BG-OCR] pipeline FAILED with form=%s", form_db_id)
        async with AsyncSessionLocal() as db:
            form = await db.get(Form, form_db_id, with_for_update=True)
            if form and form.status == FormStatus.processing:
                form.status = FormStatus.failed
                await db.commit()
                logger.info("[BG-OCR] Update status to failed with form=%s", form_db_id)
            else:
                await db.rollback()
        return

    # Kiểm tra CT01 và bản khai online có cùng một người không.
    async with AsyncSessionLocal() as db:
        is_same, same_notes = await check_same_person(result, db, form_db_id)
        if not is_same:
            logger.warning("[BG-OCR] same-person gate fail form=%s: %s", form_db_id, same_notes)
            form = await db.get(Form, form_db_id, with_for_update=True)
            if form and form.status == FormStatus.processing:
                # CT01 không phải người thay đổi cư trú -> chặn cổng luôn.
                # Không lưu raw OCR (field không qua đối chiếu, position không đáng
                # tin -> tránh vẽ ROI sai). Xoá result cũ để hiển thị ghi chú cổng.
                await db.execute(sa_delete(FormResult).where(FormResult.form_id == form.id))
                form.status = FormStatus.gate_rejected
                form.is_gate_rejected = True
                form.review_note = _build_review_note(same_notes)
                await db.commit()
            else:
                await db.rollback()
            return
        # Qua cổng nhưng CCCD lệch nhẹ (tên khớp) -> mang ghi chú mềm sang tầng 2.
        soft_notes += same_notes

    # Tầng 2: đối chiếu field vs CSDL → lưu form_result + status → extracted
    async with AsyncSessionLocal() as db:
        form = await db.get(Form, form_db_id, with_for_update=True)
        if not form or form.status != FormStatus.processing:
            logger.warning("[BG-OCR] bỏ lưu kết quả form=%s status=%s (đã đổi)", form_db_id, getattr(form, "status", None))
            await db.rollback()
            return
        try:
            verdicts = await compute_field_statuses(db, result.get("extracted_fields") or {}, form.id)
        except Exception:
            logger.exception("[BG-OCR] đối chiếu CSDL FAILED form=%s (mặc định need_review)", form_db_id)
            verdicts = {}
        # Xoá result cũ (nếu chạy lại trích xuất) để không nhân đôi dòng.
        await db.execute(sa_delete(FormResult).where(FormResult.form_id == form.id))
        for row in extracted_fields_to_results(form.id, result, verdicts):
            db.add(row)
        form.status = FormStatus.extracted
        form.is_gate_rejected = False  # đã qua cả 2 cổng → không còn gate-reject
        # Ghi chú mềm từ cổng tầng 1 (phone/email lệch) — không chặn, chỉ để cán bộ biết.
        if soft_notes:
            form.review_note = _build_review_note(soft_notes)
        await db.commit()

    # Upload warped image lên S3 và lưu path vào evidence CT01
    warped_tmp = result.get("warped_tmp_path")
    if warped_tmp:
        try:
            from app.models.form import Evidence
            from datetime import timezone as _tz
            key = s3_service.build_object_key("warped.jpg", "WARPED")
            warped_url = await loop.run_in_executor(
                None, s3_service.upload_file, warped_tmp, key, "image/jpeg"
            )
            async with AsyncSessionLocal() as db:
                ev = (await db.execute(
                    select(Evidence).where(
                        Evidence.form_id == form_db_id,
                        Evidence.path_url.ilike("%CT01%"),
                    )
                )).scalar_one_or_none()
                if ev:
                    ev.warped_img = warped_url
                    await db.commit()
                    logger.info("[BG-OCR] warped_img saved form=%s", form_db_id)
        except Exception:
            logger.exception("[BG-OCR] upload warped FAILED form=%s (bỏ qua)", form_db_id)
        finally:
            await loop.run_in_executor(None, _safe_remove, warped_tmp)

    logger.info("[BG-OCR] status → extracted form=%s (DONE)", form_db_id)


# Overdue scan
async def mark_overdue_forms(db: AsyncSession, days: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    res = await db.execute(
        sa_update(Form)
        .where(Form.status.notin_(NOT_OVERDUE_STATES), Form.created_at < cutoff)
        .values(status=FormStatus.overdue)
    )
    return res.rowcount or 0


# Re-extraction (recovery + thủ công)

# Các trạng thái cho phép kích hoạt lại trích xuất (chưa có quyết định của cán bộ → an toàn ghi đè).
RE_EXTRACTABLE_STATES: set[FormStatus] = {
    FormStatus.failed, FormStatus.overdue, FormStatus.processing,
}

# Trạng thái cho phép staff kích hoạt lại trích xuất thủ công.
# Không bao gồm: draft/submitted/processing (đang chạy), returned (đã trả kết quả).
# gate_rejected: cho chạy lại sau khi người dân bổ sung/sửa dữ liệu online (cổng sẽ pass nếu đã sửa).
MANUAL_REEXTRACT_STATES: set[FormStatus] = {
    FormStatus.failed,
    FormStatus.overdue,
    FormStatus.extracted,
    FormStatus.under_review,
    FormStatus.reviewed,
    FormStatus.gate_rejected,
}


async def resolve_extraction_inputs(form: Form, db: AsyncSession) -> tuple[str, str] | None:
    if form.form_type_id is None:
        return None
    paths = (await db.execute(
        select(Evidence.path_url).where(Evidence.form_id == form.id)
    )).scalars().all()
    ct01 = next((p for p in paths if "CT01" in p.upper()), None)
    if not ct01:
        return None
    tmpl = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.form_type_id == form.form_type_id,
            FormTemplate.is_active == True,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not tmpl:
        return None
    return ct01, tmpl.config_path


async def dispatch_reextract(form: Form, db: AsyncSession, background_tasks: BackgroundTasks) -> bool:
    inputs = await resolve_extraction_inputs(form, db)
    if inputs is None:
        return False
    ct01_path, config_path = inputs
    form.status = FormStatus.submitted
    background_tasks.add_task(process_form_bg, form.id, ct01_path, config_path)
    return True


async def requeue_stale_processing(
    db: AsyncSession, background_tasks: BackgroundTasks, minutes: int,
) -> int:
    """Tự phục hồi: form kẹt 'processing' quá `minutes` (OCR chết/restart giữa chừng)
    → kích hoạt lại trích xuất. Form thiếu input (mất ảnh/template) → đánh 'failed' cho cán bộ xử lý tay."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    forms = (await db.execute(
        select(Form).where(Form.status == FormStatus.processing, Form.updated_at < cutoff)
    )).scalars().all()
    requeued = 0
    for form in forms:
        if await dispatch_reextract(form, db, background_tasks):
            requeued += 1
            logger.info("[BG-OCR] requeue stale form=%s", form.id)
        else:
            form.status = FormStatus.failed
            logger.warning("[BG-OCR] stale form=%s thiếu input → failed", form.id)
    return requeued
