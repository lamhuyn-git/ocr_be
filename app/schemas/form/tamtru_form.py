from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TamtruFormCreate(BaseModel):
    form_id:            UUID
    case:               str | None = Field(default=None, max_length=100)
    type:               str | None = Field(default=None, max_length=100)
    location_register:  str | None = Field(default=None, max_length=512)
    registered_user_id: UUID | None = None
    register_content:   Any | None = None


class TamtruFormUpdate(BaseModel):
    case:               str | None = Field(default=None, max_length=100)
    type:               str | None = Field(default=None, max_length=100)
    location_register:  str | None = Field(default=None, max_length=512)
    registered_user_id: UUID | None = None
    register_content:   Any | None = None


class TamtruFormResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                 UUID
    form_id:            UUID
    case:               str | None
    type:               str | None
    location_register:  str | None
    registered_user_id: UUID | None
    register_content:   Any | None
    created_at:         datetime
