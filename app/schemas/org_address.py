from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from uuid import UUID


class OrgAddressCreate(BaseModel):
    org_id: UUID
    dia_chi: str = Field(min_length=1, max_length=512)
    is_active: bool = True


class OrgAddressUpdate(BaseModel):
    org_id: UUID | None = None
    dia_chi: str | None = Field(default=None, min_length=1, max_length=512)
    is_active: bool | None = None


class OrgAddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    dia_chi: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
