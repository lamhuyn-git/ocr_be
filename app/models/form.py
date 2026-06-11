from __future__ import annotations
import uuid
import enum
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Enum, Text, ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
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


REVIEW_PREDECESSORS: dict[str, set[str]] = {
    FormStatus.under_review.value: {FormStatus.extracted.value, FormStatus.failed.value},
    FormStatus.approved.value:     {FormStatus.under_review.value, FormStatus.extracted.value},
    FormStatus.rejected.value:     {FormStatus.under_review.value, FormStatus.extracted.value},
    FormStatus.returned.value:     {FormStatus.approved.value, FormStatus.rejected.value},
}


class FormType(Base):
    __tablename__ = "form_types"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type_name  = Column(String(100), unique=True, nullable=False, index=True)  # "ct01"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    templates = relationship("FormTemplate", back_populates="form_type", lazy="noload")


class FormTemplate(Base):
    """Một phiên bản cấu hình của 1 form type. is_active = bản đang dùng."""
    __tablename__ = "form_templates"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_type_id = Column(UUID(as_uuid=True), ForeignKey("form_types.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    name         = Column(String(255), nullable=False)
    version      = Column(String(50), nullable=False, default="1.0")
    config_path  = Column(String(512), nullable=False)      # YAML config trên đĩa
    field_schema = Column(JSONB, nullable=True)             # mô tả field/section để validate + render
    is_active    = Column(Boolean, default=True, nullable=False)
    created_by   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at   = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    form_type = relationship("FormType", back_populates="templates")


class Form(Base):
    __tablename__ = "forms"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_type_id = Column(UUID(as_uuid=True), ForeignKey("form_types.id", ondelete="SET NULL"),
                          nullable=True, index=True)  # loại form (resolve template active khi xử lý)
    org_id      = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"),
                         nullable=True, index=True)  # phường tiếp nhận
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
                         nullable=True, index=True)  # người nộp

    status      = Column(Enum(FormStatus), default=FormStatus.submitted, nullable=False, index=True)

    # File ảnh đã nộp
    original_filename = Column(String(255), nullable=True)
    file_path         = Column(String(512), nullable=True)
    file_size         = Column(Integer, nullable=True)

    # Review + kết quả
    reviewed_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at      = Column(DateTime(timezone=True), nullable=True)
    review_note      = Column(Text, nullable=True)
    result_message   = Column(Text, nullable=True)
    result_file_path = Column(String(512), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    detail            = relationship("DetailForm", back_populates="form", uselist=False,
                                     cascade="all, delete-orphan", lazy="noload")
    extracted_results = relationship("ExtractedResult", back_populates="form",
                                     cascade="all, delete-orphan", lazy="noload",
                                     order_by="ExtractedResult.created_at")
    history           = relationship("FormStatusHistory", back_populates="form",
                                     cascade="all, delete-orphan", lazy="noload",
                                     order_by="FormStatusHistory.created_at")


class DetailForm(Base):
    __tablename__ = "detail_forms"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id        = Column(UUID(as_uuid=True), ForeignKey("forms.id", ondelete="CASCADE"),
                            nullable=False, unique=True)
    origin_content = Column(JSONB, nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    form = relationship("Form", back_populates="detail")


class ExtractedResult(Base):
    __tablename__ = "extracted_results"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id    = Column(UUID(as_uuid=True), ForeignKey("forms.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    content    = Column(JSONB, nullable=True)              # toàn bộ output pipeline
    source     = Column(String(20), nullable=False, default="ocr")  # ocr | manual
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    form    = relationship("Form", back_populates="extracted_results")
    changes = relationship("HistoryContent", back_populates="extracted_result",
                           cascade="all, delete-orphan", lazy="noload",
                           order_by="HistoryContent.changed_at")


class HistoryContent(Base):
    __tablename__ = "history_content"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extracted_result_id = Column(UUID(as_uuid=True), ForeignKey("extracted_results.id", ondelete="CASCADE"),
                                 nullable=False, index=True)
    new_content         = Column(JSONB, nullable=True)
    changed_by          = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    changed_at          = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    extracted_result = relationship("ExtractedResult", back_populates="changes")


class FormStatusHistory(Base):
    __tablename__ = "form_status_history"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id       = Column(UUID(as_uuid=True), ForeignKey("forms.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    from_status   = Column(Enum(FormStatus), nullable=True)
    to_status     = Column(Enum(FormStatus), nullable=False)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note          = Column(Text, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    form = relationship("Form", back_populates="history")
