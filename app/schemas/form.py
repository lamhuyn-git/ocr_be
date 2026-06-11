from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Literal
from datetime import date, datetime
from uuid import UUID
from app.models.form import FormStatus


# Form types & templates

class FormTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:         UUID
    type_name:  str
    created_at: datetime


class FormTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:           UUID
    form_type_id: UUID
    name:         str
    version:      str
    is_active:    bool
    field_schema: Any | None
    created_by:   UUID | None
    created_at:   datetime


# Pydantic model for CT01
class CoQuanThucHien(BaseModel):
    province_id: UUID
    org_id: UUID


class ThuTucYeuCau(BaseModel):
    form_type_id: UUID
    type: str
    case: str


class NguoiDeNghiInfo(BaseModel):
    name: str
    birth_day: date
    gender: Literal["male", "female"]
    id_number: str = Field(min_length=9, max_length=12)
    phone_number: str | None = None      # optional
    email: str | None = None             # optional


class ThongTinNguoiDeNghi(BaseModel):
    type: Literal["themself", "declare"]
    infor: NguoiDeNghiInfo


class ThongTinDeNghi(BaseModel):
    address: str
    content: str
    due_time: date


class ThanhVienCungThayDoi(BaseModel):
    no: int
    name: str
    day_of_birth: date
    gender: Literal["male", "female"]
    id_number: str
    relation: str


class ReceiveMethod(BaseModel):
    notification_method: Literal["sms", "email"]


class FormCreate(BaseModel):
    co_quan_thuc_hien: CoQuanThucHien
    thu_tuc_yeu_cau: ThuTucYeuCau
    thong_tin_nguoi_de_nghi: ThongTinNguoiDeNghi
    thong_tin_de_nghi: ThongTinDeNghi
    thanh_vien_cung_thay_doi: list[ThanhVienCungThayDoi] = []   # rỗng nếu "themself"
    recieve_method: ReceiveMethod
    form_json: Any | None = None   # original submission content (for record-keeping, debugging, or future re-processing)





# ── Forms ───────────────────────────────────────────────────────────────────────

class FormResponse(BaseModel):
    """Lightweight list item."""
    model_config = ConfigDict(from_attributes=True)

    id:                UUID
    form_type_id:      UUID | None
    org_id:            UUID | None
    user_id:           UUID | None
    status:            FormStatus
    original_filename: str | None
    reviewed_by:       UUID | None
    reviewed_at:       datetime | None
    created_at:        datetime
    updated_at:        datetime


class FormDetailResponse(FormResponse):
    """Full detail: origin (user submission) + latest extracted result + review/result."""
    review_note:      str | None = None
    result_message:   str | None = None
    result_file_path: str | None = None
    origin_content:   Any | None = None     # DetailForm.origin_content
    extracted_content: Any | None = None    # latest ExtractedResult.content


class FormList(BaseModel):
    total:     int
    page:      int
    page_size: int
    items:     list[FormResponse]


class FormCreateResponse(BaseModel):
    form_id_db: UUID
    status:     FormStatus


class FormExtractResponse(BaseModel):
    """Synchronous extraction result (no DB persistence)."""
    form_type:          str
    confidence_score:   float | None = None
    alignment_method:   str | None = None
    alignment_quality:  str | None = None
    processing_time_ms: int | None = None
    extracted_fields:   Any | None = None
    alignment_meta:     Any | None = None


# ── Review / result ─────────────────────────────────────────────────────────────

class DecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    note:     str | None = Field(default=None, max_length=2000)


class ResultRequest(BaseModel):
    result_message:   str = Field(min_length=1, max_length=4000)
    result_file_path: str | None = Field(default=None, max_length=512)


class FormStatusHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:            UUID
    from_status:   FormStatus | None
    to_status:     FormStatus
    actor_user_id: UUID | None
    note:          str | None
    created_at:    datetime


# ── Extracted-content edit + history ─────────────────────────────────────────────

class ContentUpdateRequest(BaseModel):
    new_content: dict[str, Any]


class HistoryContentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:          UUID
    new_content: Any | None
    changed_by:  UUID | None
    changed_at:  datetime


