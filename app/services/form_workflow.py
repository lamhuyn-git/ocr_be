from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_user_membership
from app.database import AsyncSessionLocal
from app.models.form import (
    Form, FormType, FormTemplate, DetailForm, ExtractedResult,
    FormStatus, FormStatusHistory, REVIEW_PREDECESSORS,
)
from app.models.user import User
from app.schemas.form import FormDetailResponse
from app.services.form_service import run_form_pipeline

logger = logging.getLogger(__name__)


# Status / transitions

def record_status_change(db: AsyncSession, form: Form, to_status: FormStatus, actor_user_id: UUID | None, note: str | None = None) -> None:
    # Ghi history (from_status lấy tự động từ trạng thái hiện tại) + cập nhật status thật trên form.
    db.add(FormStatusHistory(form_id=form.id, from_status=form.status, to_status=to_status, actor_user_id=actor_user_id, note=note))
    form.status = to_status


def assert_transition(form: Form, to_status: FormStatus) -> None:
    if form.status.value not in REVIEW_PREDECESSORS.get(to_status.value, set()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Cannot move '{form.status.value}' → '{to_status.value}'")


# ── Lookups ───────────────────────────────────────────────────────────────────────

async def active_template_for_type(type_name: str, db: AsyncSession) -> FormTemplate:
    ft = (await db.execute(select(FormType).where(FormType.type_name == type_name.lower()))).scalar_one_or_none()
    if not ft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Form type '{type_name}' not found")
    tmpl = (
        await db.execute(
            select(FormTemplate).where(FormTemplate.form_type_id == ft.id, FormTemplate.is_active == True)  # noqa: E712
        )
    ).scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No active template for form type '{type_name}'")
    return tmpl


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


async def get_form_for_review(form_db_id: UUID, current_user: User, db: AsyncSession) -> Form:
    """Lock the form row; assert caller is super_admin or staff of the form's ward."""
    form = await db.get(Form, form_db_id, with_for_update=True)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    if not current_user.is_superuser:
        if form.org_id is None or not await get_user_membership(form.org_id, current_user, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return form


async def latest_extracted(form_id: UUID, db: AsyncSession) -> ExtractedResult | None:
    return (
        await db.execute(
            select(ExtractedResult).where(ExtractedResult.form_id == form_id)
            .order_by(desc(ExtractedResult.created_at)).limit(1)
        )
    ).scalar_one_or_none()


async def build_detail_response(form: Form, db: AsyncSession) -> FormDetailResponse:
    """Assemble FormDetailResponse = form + origin (DetailForm) + latest extracted content."""
    await db.refresh(form)  # repopulate expired attrs to avoid lazy IO during serialization
    detail = (await db.execute(select(DetailForm).where(DetailForm.form_id == form.id))).scalar_one_or_none()
    latest = await latest_extracted(form.id, db)
    resp = FormDetailResponse.model_validate(form)
    resp.origin_content = detail.origin_content if detail else None
    resp.extracted_content = latest.content if latest else None
    return resp


# Background OCR + extraction pipeline

async def process_form_bg(form_db_id: UUID, image_path: str, config_path: str) -> None:
    runnable_status = {FormStatus.submitted, FormStatus.processing}
    logger.info("[BG-OCR] START form=%s image=%s config=%s", form_db_id, image_path, config_path)

    # Bước 1: đổi status → processing
    async with AsyncSessionLocal() as db:
        form = await db.get(Form, form_db_id, with_for_update=True)
        if not form or form.status not in runnable_status:
            logger.warning("[BG-OCR] SKIP form=%s status=%s (không ở trạng thái chạy được)",
                           form_db_id, getattr(form, "status", None))
            await db.rollback()
            return
        record_status_change(db, form, FormStatus.processing, None, "OCR started")
        await db.commit()
    logger.info("[BG-OCR] status → processing form=%s", form_db_id)

    # Bước 2: chạy OCR + extraction (thread riêng, không block event loop)
    try:
        logger.info("[BG-OCR] pipeline đang chạy form=%s ...", form_db_id)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, run_form_pipeline, image_path, config_path)
        logger.info("[BG-OCR] pipeline xong form=%s", form_db_id)
    except Exception as exc:
        logger.exception("[BG-OCR] pipeline FAILED form=%s", form_db_id)
        # Đánh dấu failed (commit chắc chắn — không để form kẹt ở processing)
        async with AsyncSessionLocal() as db:
            form = await db.get(Form, form_db_id, with_for_update=True)
            if form and form.status == FormStatus.processing:
                record_status_change(db, form, FormStatus.failed, None, str(exc))
                await db.commit()
                logger.info("[BG-OCR] status → failed form=%s", form_db_id)
            else:
                logger.warning("[BG-OCR] không set failed được form=%s status=%s",
                               form_db_id, getattr(form, "status", None))
                await db.rollback()
        return

    # Bước 3: lưu kết quả + status → extracted
    async with AsyncSessionLocal() as db:
        form = await db.get(Form, form_db_id, with_for_update=True)
        if not form or form.status != FormStatus.processing:
            logger.warning("[BG-OCR] bỏ lưu kết quả form=%s status=%s (đã đổi)",
                           form_db_id, getattr(form, "status", None))
            await db.rollback()
            return
        db.add(ExtractedResult(form_id=form.id, content=result, source="ocr"))
        record_status_change(db, form, FormStatus.extracted, None, "OCR completed")
        await db.commit()
    logger.info("[BG-OCR] status → extracted form=%s (DONE)", form_db_id)
