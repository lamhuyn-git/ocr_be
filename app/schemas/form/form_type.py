from __future__ import annotations
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FormTypeCreate(BaseModel):
    type_name: str = Field(min_length=1, max_length=100, description="Mã loại form, vd 'ct01'")


class FormTypeUpdate(BaseModel):
    type_name: str = Field(min_length=1, max_length=100)


class FormTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:         UUID
    type_name:  str
    created_at: datetime
