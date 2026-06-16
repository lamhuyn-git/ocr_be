from __future__ import annotations
import logging

from app.core.email.base import EmailSender

logger = logging.getLogger(__name__)


class ConsoleEmailSender(EmailSender):
    """In email ra log thay vì gửi thật — dùng cho dev/test khi chưa cấu hình SMTP."""

    async def send(self, to: str, subject: str, html: str, text: str | None = None) -> None:
        logger.info(
            "[ConsoleEmail] To=%s | Subject=%s\n%s",
            to, subject, text or html,
        )
