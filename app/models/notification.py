from __future__ import annotations
import uuid
import enum
from sqlalchemy import (Column, String, Text, Boolean, DateTime, Enum, ForeignKey, Index,)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base


class NotificationType(str, enum.Enum):
    form_submitted = "form_submitted"
    form_returned  = "form_returned"

class ChannelType(str, enum.Enum):
    website = "website"
    email = "email"

class Notification(Base):
    __tablename__ = "notifications"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)        # ai là người nhận thông báo   
    type              = Column(Enum(NotificationType), nullable=False)
    title             = Column(String(255), nullable=False)                                                                       # tiêu đề của thông báo
    body              = Column(Text, nullable=True)                                                                               # Nội dung thông báo là gì
    form_id           = Column(UUID(as_uuid=True), ForeignKey("forms.id", ondelete="CASCADE"), nullable=True, index=True)         # bấm vào để mở hồ sơ
    form_type         = Column(String(150), nullable=True)                                                                        # tên loại hồ sơ (vd "Đăng ký tạm trú")
    is_read           = Column(Boolean, default=False, nullable=False)                                                            # Thông báo đã được đọc chưa
    channel           = Column(Enum(ChannelType), nullable=True)                                                                  # Thông báo trả về đâu
    created_at        = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)