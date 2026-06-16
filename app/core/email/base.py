from __future__ import annotations
from abc import ABC, abstractmethod


class EmailSendError(Exception):
    """Gửi email thất bại — caller tự quyết định nuốt lỗi hay không."""


class EmailSender(ABC):
    """Giao diện gửi email provider-agnostic. Đổi provider = đổi impl, không đổi caller."""

    @abstractmethod
    async def send(self, to: str, subject: str, html: str, text: str | None = None) -> None:
        ...
