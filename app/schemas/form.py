from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field
from typing import Any
from datetime import datetime
from uuid import UUID
from app.models.form import FormStatus


# ── Templates ────────────────────────────────────────────────────────────────

class FormTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:               UUID
    form_id:          str
    name:             str
    version:          str
    canonical_width:  int
    canonical_height: int
    is_active:        bool
    created_by:       UUID | None
    created_at:       datetime
    updated_at:       datetime


# ── Forms ─────────────────────────────────────────────────────────────────────

class FormResponse(BaseModel):
    """Lightweight list item — no heavy field data."""
    model_config = ConfigDict(from_attributes=True)

    id:                UUID
    org_id:            UUID | None
    created_by:        UUID | None
    template_id:       UUID | None
    form_id:           str
    original_filename: str
    file_size:         int
    status:            FormStatus
    alignment_method:  str | None
    alignment_quality: str | None
    confidence_score:  float | None
    error_message:     str | None
    processing_time_ms: int | None
    created_at:        datetime
    updated_at:        datetime


class FormDetailResponse(FormResponse):
    """Full detail — includes extracted + validated fields."""
    extracted_fields: Any | None
    validated_fields: Any | None
    alignment_meta:   Any | None


class FormList(BaseModel):
    total:     int
    page:      int
    page_size: int
    items:     list[FormResponse]


class FormCreateResponse(BaseModel):
    form_id_db: UUID
    status:     FormStatus
    message:    str
