from __future__ import annotations

import asyncio
import logging
import os
from typing import Any
from uuid import UUID

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.form import (
    Form, FormType, FormTemplate, FormResult, FormStatus,
)
from app.services.form_service import run_form_pipeline
from app.services import s3_service

logger = logging.getLogger(__name__)


# Định nghãi các ràng buộc khi change stt
ALLOWED_TRANSITIONS: dict[FormStatus, set[FormStatus]] = {
    FormStatus.under_review:   {FormStatus.extracted},                  # mở hồ sơ để xem xét (khóa)
    FormStatus.reviewed:       {FormStatus.under_review},               # xong bước kiểm tra
    FormStatus.valid:          {FormStatus.reviewed},                   # kết luận hợp lệ
    FormStatus.invalid:        {FormStatus.reviewed},                   # kết luận không hợp lệ
    FormStatus.returned:       {FormStatus.valid},                      # xác nhận cuối: đã trả kết quả
    FormStatus.require_adjust: {FormStatus.invalid},                    # xác nhận cuối: yêu cầu chỉnh sửa
}
# Draft và chính Overdue là không thể thành overdue. Stt còn lại đều được
NOT_OVERDUE_STATES: set[FormStatus] = {FormStatus.draft, FormStatus.overdue}


def assert_can_transition(form: Form, to_status: FormStatus) -> None:
    allowed = ALLOWED_TRANSITIONS.get(to_status)
    if allowed is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Status '{to_status.value}' không thể chuyển thủ công")
    if form.status not in allowed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Không thể chuyển '{form.status.value}' → '{to_status.value}'")


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


# Lookups

async def active_template_for_type_id(form_type_id: UUID, db: AsyncSession) -> FormTemplate:
    tmpl = (
        await db.execute(
            select(FormTemplate).where(FormTemplate.form_type_id == form_type_id, FormTemplate.is_active == True)  # noqa: E712
        )
    ).scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No active template for form type id '{form_type_id}'")
    return tmpl


async def get_form_or_404(form_db_id: UUID, db: AsyncSession) -> Form:
    form = await db.get(Form, form_db_id)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    return form


# Map pipeline output → form_result rows

def extracted_fields_to_results(form_id: UUID, result: dict[str, Any]) -> list[FormResult]:
    """Một field OCR → một dòng form_result.
    raw_value = text thô, suggested_value = text đã chuẩn hoá (gợi ý cho cán bộ)."""
    fields = result.get("extracted_fields") or {}
    rows: list[FormResult] = []
    for position, (label, field) in enumerate(fields.items()):
        if isinstance(field, dict):
            raw = field.get("text_raw")
            suggested = field.get("text")
        else:
            raw, suggested = None, (str(field) if field is not None else None)
        rows.append(FormResult(
            form_id=form_id, position=position, label=label,
            raw_value=raw, suggested_value=suggested,
        ))
    return rows


# Background extraction workflow
async def process_form_bg(form_db_id: UUID, image_path: str, config_path: str) -> None:
    runnable_status = {FormStatus.submitted, FormStatus.processing}
    logger.info("[BG-OCR] START form=%s image=%s config=%s", form_db_id, image_path, config_path)

    # ubmitted → processing
    async with AsyncSessionLocal() as db:
        form = await db.get(Form, form_db_id, with_for_update=True)
        if not form or form.status not in runnable_status:
            logger.warning("[BG-OCR] SKIP form=%s status=%s (không ở trạng thái chạy được)",
                           form_db_id, getattr(form, "status", None))
            await db.rollback()
            return
        form.status = FormStatus.processing
        await db.commit()
    logger.info("[BG-OCR] status → processing form=%s", form_db_id)

    # Tải ảnh từ S3 về file tạm → chạy OCR + extraction (thread riêng, không block event loop)
    try:
        loop = asyncio.get_running_loop()
        local_image = await loop.run_in_executor(None, s3_service.download_to_temp, image_path)
        try:
            result = await loop.run_in_executor(None, run_form_pipeline, local_image, config_path)
        finally:
            await loop.run_in_executor(None, _safe_remove, local_image)
        logger.info("[BG-OCR] pipeline xong form=%s", form_db_id)
    except Exception as exc:
        logger.exception("[BG-OCR] pipeline FAILED form=%s", form_db_id)
        async with AsyncSessionLocal() as db:
            form = await db.get(Form, form_db_id, with_for_update=True)
            if form and form.status == FormStatus.processing:
                form.status = FormStatus.failed
                await db.commit()
                logger.info("[BG-OCR] status → failed form=%s", form_db_id)
            else:
                await db.rollback()
        return

    # Bước 3: lưu form_result + status → extracted
    async with AsyncSessionLocal() as db:
        form = await db.get(Form, form_db_id, with_for_update=True)
        if not form or form.status != FormStatus.processing:
            logger.warning("[BG-OCR] bỏ lưu kết quả form=%s status=%s (đã đổi)",
                           form_db_id, getattr(form, "status", None))
            await db.rollback()
            return
        for row in extracted_fields_to_results(form.id, result):
            db.add(row)
        form.status = FormStatus.extracted
        await db.commit()
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
