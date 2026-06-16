from __future__ import annotations
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FormResultCreate(BaseModel):
    form_id:         UUID
    position:        int = 0
    label:           str = Field(min_length=1, max_length=255)
    raw_value:       str | None = None
    suggested_value: str | None = None
    final_value:     str | None = None
    confirmed_by:    UUID | None = None


class FormResultUpdate(BaseModel):
    position:        int | None = None
    label:           str | None = Field(default=None, max_length=255)
    raw_value:       str | None = None
    suggested_value: str | None = None
    final_value:     str | None = None
    confirmed_by:    UUID | None = None


class FormResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:              UUID
    form_id:         UUID
    position:        int
    label:           str
    raw_value:       str | None
    suggested_value: str | None
    final_value:     str | None
    confirmed_by:    UUID | None
    created_at:      datetime


class FormResultConfirmRequest(BaseModel):
    """Cán bộ chốt giá trị 1 field. final_value None → chấp nhận suggested_value."""
    final_value: str | None = Field(default=None, max_length=4000)
