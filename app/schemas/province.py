from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from uuid import UUID


class ProvinceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, max_length=100, description="Tự sinh từ name nếu bỏ trống")


class ProvinceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    slug: str | None = Field(default=None, max_length=100)


class ProvinceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime
