from __future__ import annotations
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvidenceInput(BaseModel):
    path_url: str = Field(min_length=1, max_length=512) 


class EvidenceCreate(BaseModel):
    form_id:  UUID
    path_url: str = Field(min_length=1, max_length=512)


class EvidenceUpdate(BaseModel):
    path_url: str = Field(min_length=1, max_length=512)


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:          UUID
    form_id:     UUID
    path_url:    str
    warped_img:  str | None
    created_at:  datetime


class FormEvidencesDetail(BaseModel):
    """Nhóm các path ảnh đính kèm trả về trong detail form (đã presign)."""
    warped_img:      str | None = None  # ảnh đã align từ CT01
    residence_proof: str | None = None  # giấy tờ cư trú
