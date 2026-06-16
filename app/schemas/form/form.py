"""Schema cho bảng gốc Form: list item, detail (gộp subtype/evidences/results), responses."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.form import FormStatus
from app.schemas.form.evidence import EvidenceCreate, EvidenceResponse
from app.schemas.form.form_result import FormResultResponse
from app.schemas.form.tamtru_form import TamtruFormCreate, TamtruFormResponse


class FormCreate(BaseModel):
    org_id: UUID
    form_type_id: UUID
    submit_by: UUID
    notification_on: str | None = None   # nơi nhận thông báo cuối cùng (email/sđt)
    evidences: list[EvidenceCreate]
    form_spec: TamtruFormCreate


class FormDraftCreate(BaseModel):
    org_id: UUID | None = None
    form_type_id: UUID | None = None
    submit_by: UUID
    notification_on: str | None = None
    evidences: list[EvidenceCreate] = []
    form_spec: TamtruFormCreate | None = None


class FormDraftUpdate(BaseModel):
    org_id: UUID | None = None
    form_type_id: UUID | None = None
    notification_on: str | None = None
    evidences: list[EvidenceCreate] | None = None
    form_spec: TamtruFormCreate | None = None


class FormCreateResponse(BaseModel):
    form_id_db: UUID
    status:     FormStatus


class FormResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:           UUID
    form_type_id: UUID | None
    org_id:       UUID | None
    submit_by:    UUID | None
    status:       FormStatus
    notification_on: str | None
    created_at:   datetime
    updated_at:   datetime


class FormDetailResponse(FormResponse):
    tamtru:    TamtruFormResponse | None = None
    evidences: list[EvidenceResponse] = []
    results:   list[FormResultResponse] = []


class FormList(BaseModel):
    total:     int
    page:      int
    page_size: int
    items:     list[FormResponse]




class FormExtractResponse(BaseModel):
    form_type:          str
    confidence_score:   float | None = None
    alignment_method:   str | None = None
    alignment_quality:  str | None = None
    processing_time_ms: int | None = None
    extracted_fields:   Any | None = None
    alignment_meta:     Any | None = None
