from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationType, ChannelType


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: NotificationType
    title: str
    body: str | None = None
    form_id: UUID | None = None
    form_type: str | None = None
    is_read: bool
    channel: ChannelType | None = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationOut]
    total: int
    unread: int
    page: int
    page_size: int


class MarkReadRequest(BaseModel):
    ids: list[UUID] | None = None
    all: bool = False
