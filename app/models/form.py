from __future__ import annotations
import uuid
import enum
from sqlalchemy import (
    Column, String, Integer, Float, DateTime,
    Boolean, Enum, Text, ForeignKey, JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base


class FormStatus(str, enum.Enum):
    pending    = "pending"
    processing = "processing"
    completed  = "completed"
    failed     = "failed"


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

    status            = Column(Enum(FormStatus), default=FormStatus.pending, nullable=False, index=True)

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

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)
