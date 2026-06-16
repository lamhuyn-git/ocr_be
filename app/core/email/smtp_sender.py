from __future__ import annotations
import logging
from email.message import EmailMessage

import aiosmtplib

from app.config import get_settings
from app.core.email.base import EmailSender, EmailSendError

logger = logging.getLogger(__name__)
settings = get_settings()


class SmtpEmailSender(EmailSender):
    """Gửi email qua SMTP async (aiosmtplib). Trỏ tới SES/Mailgun/Gmail... qua .env."""

    async def send(self, to: str, subject: str, html: str, text: str | None = None) -> None:
        msg = EmailMessage()
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        # Bản text trước, html sau → client ưu tiên hiển thị html nếu hỗ trợ.
        msg.set_content(text or "Vui lòng mở email bằng ứng dụng hỗ trợ HTML.")
        msg.add_alternative(html, subtype="html")

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user or None,
                password=settings.smtp_password or None,
                start_tls=settings.smtp_use_tls,
            )
        except Exception as exc:  # noqa: BLE001 - gom mọi lỗi SMTP về một loại
            logger.error("SMTP send failed to %s: %s", to, exc)
            raise EmailSendError(str(exc)) from exc
