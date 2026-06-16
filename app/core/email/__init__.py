from __future__ import annotations
import logging
from functools import lru_cache

from app.config import get_settings
from app.core.email.base import EmailSender, EmailSendError
from app.core.email.console_sender import ConsoleEmailSender
from app.core.email.smtp_sender import SmtpEmailSender
from app.core.email.renderer import render_otp_email

logger = logging.getLogger(__name__)


@lru_cache
def get_email_sender() -> EmailSender:
    settings = get_settings()
    backend = settings.email_sender_backend.lower()
    if backend == "console":
        return ConsoleEmailSender()
    # smtp nhưng thiếu host → fallback console để dev không bị chặn.
    if not settings.smtp_host:
        logger.warning("SMTP host chưa cấu hình → dùng ConsoleEmailSender.")
        return ConsoleEmailSender()
    return SmtpEmailSender()


__all__ = ["get_email_sender", "render_otp_email", "EmailSender", "EmailSendError"]
