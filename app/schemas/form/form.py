"""Schema cho bảng gốc Form: list item, detail (gộp subtype/evidences/results), responses."""
from __future__ import annotations
from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.form import FormStatus
from app.models.residence import TempResidenceStatus
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


class FormReturnRequest(BaseModel):
    form_id:  UUID
    outcome:  TempResidenceStatus
    note:     str | None = Field(default=None, max_length=4000)
    dia_chi:  str | None = None
    tu_ngay:  date | None = None
    den_ngay: date | None = None


class UserFormListItem(BaseModel):
    id:             UUID
    code:           str
    status:         str
    outcome:        str | None = None
    location:       str | None = None
    created_at:     datetime
    completed_at:   datetime | None = None
    reject_reason:  str | None = None
    notify_method:  str | None = None


class UserFormCounts(BaseModel):
    all:       int = 0
    draft:     int = 0
    submitted: int = 0   
    returned:  int = 0   


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
    is_gate_rejected:  bool = False  # hồ sơ đang bị chặn ở cổng (UI chọn popup gate-reject)
    outcome:           str | None = None          # valid | require_adjust | None (chưa trả)
    returned_at:       datetime | None = None      # thời điểm trả kết quả
    returned_by_name:  str | None = None           # cán bộ xác nhận trả kết quả
    returned_by_email: str | None = None
    sumited_content:   TamtruFormDetailResponse | None
    evidences:         FormEvidencesDetail = FormEvidencesDetail()
    validated_results: list[FormResultDetailResponse] = []


FormDetailResponse.model_rebuild()


class UserFormDetailResponse(BaseModel):
    """Chi tiết hồ sơ cho citizen xem lại CHÍNH hồ sơ mình nộp.

    Chỉ chứa nội dung user đã khai (form + tamtru + evidences). Không kèm dữ liệu duyệt
    nội bộ (validated_results, result_history, db_value, confirmed_by_email, review_note,
    is_gate_rejected) — khác hẳn FormDetailResponse dành cho cán bộ.
    """
    id:               UUID
    form_type_id:     UUID | None
    org_id:           UUID | None
    status:           str  # giá trị hiển thị: draft | submitted | returned
    notification_on:  str | None = None
    created_at:       datetime
    updated_at:       datetime
    ogr_detailliated: OrgDetailResponse | None = None
    form_type_detail: FormTypeResponse | None = None
    sumited_content:  TamtruFormDetailResponse | None = None
    evidences:        FormEvidencesDetail = FormEvidencesDetail()
    outcome:          str | None = None
    result_note:      str | None = None
    returned_at:      datetime | None = None


UserFormDetailResponse.model_rebuild()


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
