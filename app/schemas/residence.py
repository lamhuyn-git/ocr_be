from __future__ import annotations
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.residence import TempResidenceStatus


class TemporaryResidenceListItem(BaseModel):
    id:            UUID
    citizen_cccd:  str | None = None   # citizen.so_dinh_danh
    citizen_name:  str | None = None   # citizen.ho_chu_dem_va_ten
    phone:         str | None = None   # citizen.so_dien_thoai
    chu_ho_cccd:   str | None = None   # citizen.so_dinh_danh_chu_ho
    dia_chi:       str
    tu_ngay:       date | None = None
    den_ngay:      date | None = None
    reviewer_name: str | None = None   # form.reviewer (users.full_name)
    form_id:       UUID | None = None  # source form → /form-detail
    status:        TempResidenceStatus
    created_at:    datetime


class TemporaryResidenceListResponse(BaseModel):
    items: list[TemporaryResidenceListItem]
    total: int
