from __future__ import annotations
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvidenceCreate(BaseModel):
    form_id:  UUID
    path_url: str = Field(min_length=1, max_length=512)


class EvidenceUpdate(BaseModel):
    path_url: str = Field(min_length=1, max_length=512)


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:         UUID
    form_id:    UUID
    path_url:   str
    created_at: datetime
