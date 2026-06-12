import enum
import uuid

from sqlalchemy import Column, String, Date, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class TempResidenceStatus(str, enum.Enum):
    active = "active"        # đang hiệu lực
    expired = "expired"      # hết hạn
    cancelled = "cancelled"  # đã huỷ (chuyển đi / thu hồi)


class TemporaryResidence(Base):
    """Bản ghi đăng ký tạm trú đã cấp cho một citizen (kết quả của form được duyệt).
    Có thời hạn (tu_ngay → den_ngay), lặp lại nhiều lần theo thời gian."""
    __tablename__ = "temporary_residences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    citizen_id = Column(UUID(as_uuid=True), ForeignKey("citizens.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    dia_chi = Column(String(512), nullable=False)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"),
                    nullable=True, index=True)  # phường cấp/quản lý
    tu_ngay = Column(Date, nullable=True)
    den_ngay = Column(Date, nullable=True)
    status = Column(Enum(TempResidenceStatus), nullable=False, server_default="active", index=True)
    form_id = Column(UUID(as_uuid=True), ForeignKey("forms.id", ondelete="SET NULL"),
                     nullable=True, index=True)  # form nguồn đã duyệt (provenance)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    citizen = relationship("Citizen", lazy="noload")
    organization = relationship("Organization", lazy="noload")
    form = relationship("Form", lazy="noload")
