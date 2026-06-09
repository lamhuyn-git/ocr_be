from __future__ import annotations
import uuid
import enum
from sqlalchemy import (
    Column, String, Integer, Float, DateTime,
    Boolean, Enum, Text, ForeignKey, JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class FormStatus(str, enum.Enum):
    submitted    = "submitted"     # người dân vừa nộp, chờ OCR
    processing   = "processing"    # OCR đang chạy
    extracted    = "extracted"     # OCR xong, chờ cán bộ duyệt
    under_review = "under_review"  # cán bộ đang duyệt
    approved     = "approved"      # cán bộ chấp thuận
    rejected     = "rejected"      # cán bộ từ chối
    returned     = "returned"      # đã trả kết quả cho người dân
    failed       = "failed"        # OCR/xử lý lỗi


# Trạng thái hợp lệ ngay trước khi chuyển sang trạng thái mới (dùng cho precondition khi duyệt).
REVIEW_PREDECESSORS: dict[str, set[str]] = {
    FormStatus.under_review.value: {FormStatus.extracted.value, FormStatus.failed.value},
    FormStatus.approved.value:     {FormStatus.under_review.value, FormStatus.extracted.value},
    FormStatus.rejected.value:     {FormStatus.under_review.value, FormStatus.extracted.value},
    FormStatus.returned.value:     {FormStatus.approved.value, FormStatus.rejected.value},
}


class FormTemplate(Base):
    """
    Represents one registered form type (e.g. CT01).
    Admin uploads a YAML config → validated → stored here.
    New form types = new rows; no code changes needed.
    """
    __tablename__ = "form_templates"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id          = Column(String(100), unique=True, nullable=False, index=True)  # "ct01"
    name             = Column(String(255), nullable=False)
    version          = Column(String(50),  nullable=False, default="1.0")
    config_path      = Column(String(512), nullable=False)   # abs path to YAML on disk
    canonical_width  = Column(Integer, default=1654)
    canonical_height = Column(Integer, default=2339)
    is_active        = Column(Boolean, default=True, nullable=False)
    created_by       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at       = Column(DateTime(timezone=True), server_default=func.now(),
                              onupdate=func.now(), nullable=False)


class Form(Base):
    """
    One submitted form image + its full extraction result.
    """
    __tablename__ = "forms"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id           = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"),
                              nullable=True, index=True)
    created_by       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
                              nullable=True, index=True)
    template_id      = Column(UUID(as_uuid=True), ForeignKey("form_templates.id", ondelete="SET NULL"),
                              nullable=True, index=True)
    form_id          = Column(String(100), nullable=False, index=True)  # denormalised for fast queries

    original_filename = Column(String(255), nullable=False)
    file_path         = Column(String(512), nullable=False)
    file_size         = Column(Integer, nullable=False)

    status            = Column(Enum(FormStatus), default=FormStatus.submitted, nullable=False, index=True)

    # Alignment metadata
    alignment_method  = Column(String(50),  nullable=True)
    alignment_quality = Column(String(20),  nullable=True)
    alignment_meta    = Column(JSON, nullable=True)

    # Extraction results
    extracted_fields  = Column(JSON, nullable=True)   # raw OCR output per field
    validated_fields  = Column(JSON, nullable=True)   # after validator cleaning
    confidence_score  = Column(Float, nullable=True)

    error_message     = Column(Text, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)

    # Review + result delivery (cán bộ duyệt → trả kết quả cho người dân)
    reviewed_by       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at       = Column(DateTime(timezone=True), nullable=True)
    review_note       = Column(Text, nullable=True)     # lý do (đặc biệt khi từ chối)
    result_message    = Column(Text, nullable=True)     # nội dung trả về người dân
    result_file_path  = Column(String(512), nullable=True)  # văn bản kết quả (optional)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    history = relationship(
        "FormStatusHistory",
        back_populates="form",
        lazy="noload",
        cascade="all, delete-orphan",
        order_by="FormStatusHistory.created_at",
    )


class FormStatusHistory(Base):
    """
    Append-only log of one form's status transitions ("lịch sử của 1 form").
    One row per transition: ai, khi nào, từ trạng thái nào sang trạng thái nào, ghi chú.
    """
    __tablename__ = "form_status_history"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id       = Column(UUID(as_uuid=True), ForeignKey("forms.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    from_status   = Column(Enum(FormStatus), nullable=True)   # null ở lần ghi đầu (submitted)
    to_status     = Column(Enum(FormStatus), nullable=False)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note          = Column(Text, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    form = relationship("Form", back_populates="history")
