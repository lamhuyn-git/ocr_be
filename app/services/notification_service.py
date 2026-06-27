from __future__ import annotations
import logging
from uuid import UUID
from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.form import Form, FormType
from app.models.user import User
from app.models.organization import OrganizationMember, OrgRole, Organization
from app.models.notification import Notification, NotificationType, ChannelType
from app.models.residence import TemporaryResidence
from app.core.email import get_email_sender, render_form_returned_email, EmailSendError
from app.realtime.connection_manager import manager

logger = logging.getLogger(__name__)
settings = get_settings()


async def notify_form_submitted(form_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        form = await db.get(Form, form_id)
        if form is None or form.org_id is None:
            logger.warning("Notify_form_submitted func: form/phường không hợp lệ (id=%s)", form_id)
            return

        # Lấy tất cả cán bộ của phường nhận hồ sơ
        officer_ids = (
            await db.execute(
                select(OrganizationMember.user_id).where( OrganizationMember.org_id == form.org_id, OrganizationMember.role == OrgRole.ward_officer,)
            )
        ).scalars().all()

        # Lấy superadmin 
        superadmin_ids = (await db.execute(select(User.id).where(User.is_superuser))).scalars().all()

        recipient_ids = set(officer_ids) | set(superadmin_ids)

        if not recipient_ids:
            logger.info("Notify_form_submitted func: không có người nhận cho phường %s", form.org_id)
            return

        # Tên loại hồ sơ để hiển thị nhãn động trên UI (vd "Đăng ký tạm trú")
        form_type_label = None
        if form.form_type_id:
            ft = await db.get(FormType, form.form_type_id)
            form_type_label = ft.type_name if ft else None

        title = "Có hồ sơ mới được nhận"
        body = f"Có hồ sơ mới vừa được nộp (mã hồ sơ là {str(form.id)})."

        # Tạo thông báo cho mỗi người nhận và lưu lại trong DB
        notifications = []
        for uid in recipient_ids:                               
            n = Notification(
                recipient_user_id=uid,
                type=NotificationType.form_submitted,
                title=title,
                body=body,
                form_id=form.id,
                form_type=form_type_label,
                channel=ChannelType.website,
            )
            notifications.append(n)

        db.add_all(notifications)
        await db.commit()

        # Log quan sát: ai là người nhận, ai đang online ngay lúc này
        online = [str(uid) for uid in recipient_ids if manager.is_online(uid)]
        logger.info(
            "notify_form_submitted: form=%s recipients=%d online=%s",
            form.id, len(recipient_ids), online,
        )

        # Đẩy real-time tới admin đang online
        for n in notifications:
            await db.refresh(n)
            message = {
                "event": "notification",
                "data": {
                    "id": str(n.id),
                    "type": n.type.value,
                    "title": n.title,
                    "body": n.body,
                    "form_id": str(n.form_id) if n.form_id else None,
                    "form_type": n.form_type,
                    "is_read": n.is_read,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                },
            }
            await manager.send_to_user(n.recipient_user_id, message)


async def notify_form_returned(form_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        form = await db.get(Form, form_id)
        if form is None or form.submit_by is None:
            logger.warning("notify_form_returned: form/submit_by không hợp lệ (id=%s)", form_id)
            return

        user = await db.get(User, form.submit_by)

        tr = (await db.execute(
            select(TemporaryResidence).where(TemporaryResidence.form_id == form_id)
        )).scalars().first()
        is_valid = tr is not None
        outcome_label = "Đã duyệt" if is_valid else "Cần chỉnh sửa"

        ward = await db.get(Organization, form.org_id) if form.org_id else None
        ward_name = ward.name if ward else None

        form_type_label = None
        if form.form_type_id:
            ft = await db.get(FormType, form.form_type_id)
            form_type_label = ft.type_name if ft else None

        title = "Hồ sơ đã được duyệt" if is_valid else "Hồ sơ cần chỉnh sửa"
        body = (
            f"Vui lòng đến {ward_name} để nhận kết quả." if is_valid
            else (form.review_note or "Hồ sơ cần chỉnh sửa, vui lòng kiểm tra.")
        )

        method = (form.notification_on or "").strip().lower()

        if method == "email":
            to = user.email if user else None
            if to:
                html, text = render_form_returned_email(
                    outcome_label, ward_name, form.review_note, str(form.id)
                )
                try:
                    await get_email_sender().send(
                        to=to,
                        subject=f"{settings.app_name} — Kết quả hồ sơ",
                        html=html,
                        text=text,
                    )
                except EmailSendError:
                    logger.warning("Gửi email kết quả thất bại form=%s", form_id)
            else:
                logger.info("notify_form_returned: email channel nhưng user không có email form=%s", form_id)
            return

        n = Notification(
            recipient_user_id=form.submit_by,
            type=NotificationType.form_returned,
            title=title,
            body=body,
            form_id=form.id,
            form_type=form_type_label,
            channel=ChannelType.website,
        )
        db.add(n)
        await db.commit()
        await db.refresh(n)

        await manager.send_to_user(form.submit_by, {
            "event": "notification",
            "data": {
                "id": str(n.id),
                "type": n.type.value,
                "title": n.title,
                "body": n.body,
                "form_id": str(n.form_id) if n.form_id else None,
                "form_type": n.form_type,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            },
        })