import uuid
from app.database import Base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (Column, String, DateTime, Integer, Text, ForeignKey)


class FormResult(Base):
    __tablename__ = "form_results"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id         = Column(UUID(as_uuid=True), ForeignKey("forms.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    position        = Column(Integer, nullable=False, default=0)   # thứ tự field trên đơn
    label           = Column(String(255), nullable=False)          # tên field (vd "ho_ten")
    raw_value       = Column(Text, nullable=True)                  # giá trị OCR thô
    suggested_value = Column(Text, nullable=True)                  # giá trị đã chuẩn hoá (gợi ý), có thể null
    final_value     = Column(Text, nullable=True)                  # giá trị cán bộ chốt, có thể null
    confirmed_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    form = relationship("Form", back_populates="results")
