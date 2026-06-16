from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FormTemplateUpdate(BaseModel):
    name:         str | None = Field(default=None, max_length=255)
    version:      str | None = Field(default=None, max_length=50)
    is_active:    bool | None = None
    field_schema: Any | None = None


class FormTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:           UUID
    form_type_id: UUID
    name:         str
    version:      str
    is_active:    bool
    field_schema: Any | None
    created_by:   UUID | None
    created_at:   datetime
