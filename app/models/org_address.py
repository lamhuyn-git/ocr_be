import uuid

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class OrgAddress(Base):
    """Địa chỉ do một phường/xã (organization) quản lý.

    Dùng để xác định địa chỉ đăng ký tạm trú có THUỘC phường tiếp nhận không
    (location_register phải khớp một bản ghi của phường đó). Bảng nhỏ theo từng
    phường, nạp toàn bộ để so fuzzy.
    """
    __tablename__ = "org_addresses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
                    nullable=False, index=True)          # phường/xã quản lý địa chỉ này
    dia_chi = Column(String(512), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", lazy="noload")
