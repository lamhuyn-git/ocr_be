from __future__ import annotations
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.form import FormResultStatus, ResultConfirmStatus


class FormResultCreate(BaseModel):
    form_id:         UUID
    position:        list[float] | None = None
    label:           str = Field(min_length=1, max_length=255)
    raw_value:       str | None = None
    suggested_value: str | None = None
    status:          FormResultStatus = FormResultStatus.need_review


class FormResultUpdate(BaseModel):
    position:        list[float] | None = None
    label:           str | None = Field(default=None, max_length=255)
    raw_value:       str | None = None
    suggested_value: str | None = None
    status:          FormResultStatus | None = None


class FormResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:              UUID
    form_id:         UUID
    position:        list[float] | None
    label:           str
    raw_value:       str | None
    suggested_value: str | None
    note:            str | None
    status:          FormResultStatus
    created_at:      datetime


class FormResultDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:              UUID
    position:        list[float] | None
    label:           str
    raw_value:       str | None
    suggested_value: str | None
    note:            str | None
    status:          FormResultStatus
    created_at:      datetime


class AdminSaveChangeFieldItem(BaseModel):
    id:     UUID
    status: ResultConfirmStatus


class AdminSaveChangeRequest(BaseModel):
    form_id:        UUID
    confirmed_by:   UUID | None = None
    updated_fields: list[AdminSaveChangeFieldItem] | None = None
