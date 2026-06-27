from __future__ import annotations
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Chấp nhận cả YYYY-MM-DD và DD/MM/YYYY
def _parse_date(v) -> date | None:
    if v is None or isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Ngày không hợp lệ: '{s}' (cần DD/MM/YYYY hoặc YYYY-MM-DD)")


class TamtruFormInput(BaseModel):
    case:                   str | None = Field(default=None, max_length=100)
    type:                   str | None = Field(default=None, max_length=100)
    submit_type:            str | None = Field(default=None, max_length=100)
    location_register:      str | None = Field(default=None, max_length=512)
    registered_user_cccd:   str | None = Field(default=None, max_length=12)
    registered_user_name:   str | None = Field(default=None, max_length=255)
    registered_user_birth:  date | None = None
    registered_user_gender: str | None = Field(default=None, max_length=20)
    registered_user_phone:  str | None = Field(default=None, max_length=20)
    registered_user_mail:   str | None = Field(default=None, max_length=255)
    register_content:       str | None = None
    residence_until:        date | None = None  # thời hạn tạm trú đề nghị (đến ngày)

    _parse_birth = field_validator("registered_user_birth", mode="before")(_parse_date)
    _parse_until = field_validator("residence_until", mode="before")(_parse_date)


class TamtruFormCreate(BaseModel):
    form_id:                UUID
    case:                   str | None = Field(default=None, max_length=100)
    type:                   str | None = Field(default=None, max_length=100)
    submit_type:            str | None = Field(default=None, max_length=100)
    location_register:      str | None = Field(default=None, max_length=512)
    registered_user_cccd:   str | None = Field(default=None, max_length=12)
    registered_user_name:   str | None = Field(default=None, max_length=255)
    registered_user_birth:  date | None = None
    registered_user_gender: str | None = Field(default=None, max_length=20)
    registered_user_phone:  str | None = Field(default=None, max_length=20)
    registered_user_mail:   str | None = Field(default=None, max_length=255)
    register_content:       str | None = None

    _parse_birth = field_validator("registered_user_birth", mode="before")(_parse_date)


class TamtruFormUpdate(BaseModel):
    case:                   str | None = Field(default=None, max_length=100)
    type:                   str | None = Field(default=None, max_length=100)
    submit_type:            str | None = Field(default=None, max_length=100)
    location_register:      str | None = Field(default=None, max_length=512)
    registered_user_cccd:   str | None = Field(default=None, max_length=12)
    registered_user_name:   str | None = Field(default=None, max_length=255)
    registered_user_birth:  date | None = None
    registered_user_gender: str | None = Field(default=None, max_length=20)
    registered_user_phone:  str | None = Field(default=None, max_length=20)
    registered_user_mail:   str | None = Field(default=None, max_length=255)
    register_content:       str | None = None

    _parse_birth = field_validator("registered_user_birth", mode="before")(_parse_date)


class TamtruFormResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                     UUID
    form_id:                UUID
    case:                   str | None
    type:                   str | None
    submit_type:            str | None
    location_register:      str | None
    registered_user_cccd:   str | None
    registered_user_name:   str | None
    registered_user_birth:  date | None
    registered_user_gender: str | None
    registered_user_phone:  str | None
    registered_user_mail:   str | None
    register_content:       str | None
    residence_until:        date | None = None
    created_at:             datetime


class TamtruFormDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                     UUID
    case:                   str | None
    type:                   str | None
    submit_type:            str | None
    location_register:      str | None
    registered_user_cccd:   str | None
    registered_user_name:   str | None
    registered_user_birth:  date | None
    registered_user_gender: str | None
    registered_user_phone:  str | None
    registered_user_mail:   str | None
    register_content:       str | None
    residence_until:        date | None = None
