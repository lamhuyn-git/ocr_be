"""Schema cho bảng gốc Form: list item, detail (gộp subtype/evidences/results), responses."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.form import FormStatus
from app.schemas.form.evidence import EvidenceInput, FormEvidencesDetail
from app.schemas.form.form_result import FormResultDetailResponse
from app.schemas.form.tamtru_form import TamtruFormInput, TamtruFormDetailResponse
from app.schemas.organization import OrgDetailResponse
from app.schemas.form.form_type import FormTypeResponse

class FormCreate(BaseModel):
    org_id: UUID
    form_type_id: UUID
    submit_by: UUID
    notification_on: str | None = None 
    evidences: list[EvidenceInput] | None
    form_spec: TamtruFormInput | None


class FormDraftCreate(BaseModel):
    org_id: UUID | None = None
    form_type_id: UUID | None = None
    submit_by: UUID
    notification_on: str | None = None
    evidences: list[EvidenceInput] = []
    form_spec: TamtruFormInput | None = None


class FormDraftUpdate(BaseModel):
    org_id: UUID | None = None
    form_type_id: UUID | None = None
    notification_on: str | None = None
    evidences: list[EvidenceInput] | None = None
    form_spec: TamtruFormInput | None = None


class FormTransitionRequest(BaseModel):
    to_status: FormStatus
    note: str | None = Field(default=None, max_length=4000)


class UserFormListItem(BaseModel):
    id:             UUID
    code:           str                
    status:         FormStatus
    location:       str | None = None  
    created_at:     datetime           
    completed_at:   datetime | None = None  
    reject_reason:  str | None = None   
    notify_method:  str | None = None   


class UserFormCounts(BaseModel):
    all:        int = 0
    submitted:  int = 0   
    draft:      int = 0
    processing: int = 0   
    valid:      int = 0   
    invalid:    int = 0  


class UserFormListResponse(BaseModel):
    items:  list[UserFormListItem]
    total:  int            
    counts: UserFormCounts


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
    review_note:  str | None
    created_at:   datetime
    updated_at:   datetime


class FormDetailResponse(FormResponse):
    ogr_detailliated:  OrgDetailResponse | None
    form_type_detail:  FormTypeResponse | None
    submit_by:         UUID | None
    notification_on:   str | None
    review_note:       str | None
    sumited_content:   TamtruFormDetailResponse | None
    evidences:         FormEvidencesDetail = FormEvidencesDetail()
    validated_results: list[FormResultDetailResponse] = []


FormDetailResponse.model_rebuild()


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
