from __future__ import annotations
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.citizen import Gender, MaritalStatus, ResidenceStatus, LifeStatus


class CitizenBase(BaseModel):
    """Các trường dân cư có thể ghi (không gồm so_dinh_danh — bất biến, đặt ở Create)."""
    ho_chu_dem_va_ten: str | None = None
    ten_goi_khac: str | None = None
    ngay_sinh: date | None = None
    gioi_tinh: Gender | None = None
    noi_sinh: str | None = None
    noi_dang_ky_khai_sinh: str | None = None
    que_quan: str | None = None
    dan_toc: str | None = None
    ton_giao: str | None = None
    quoc_tich: str | None = None
    nhom_mau: str | None = None
    noi_thuong_tru: str | None = None
    noi_tam_tru: str | None = None
    noi_o_hien_tai: str | None = None
    tinh_trang_cu_tru: ResidenceStatus | None = None
    ma_ho: str | None = None
    quan_he_voi_chu_ho: str | None = None
    so_dinh_danh_chu_ho: str | None = None
    tinh_trang_hon_nhan: MaritalStatus | None = None
    nghe_nghiep: str | None = None
    tinh_trang_song: LifeStatus | None = None
    ngay_mat: date | None = None
    so_dien_thoai: str | None = None
    email: str | None = None


class CitizenCreate(CitizenBase):
    so_dinh_danh: str = Field(min_length=9, max_length=12, description="Số định danh cá nhân (vĩnh viễn)")
    ho_chu_dem_va_ten: str = Field(min_length=1, max_length=255)
    user_id: UUID | None = None  # liên kết tài khoản User (optional)


class CitizenUpdate(CitizenBase):
    """Tất cả optional — chỉ cập nhật field được gửi. so_dinh_danh bất biến nên không cho đổi."""
    pass


class CitizenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    so_dinh_danh: str
    ho_chu_dem_va_ten: str
    ten_goi_khac: str | None
    ngay_sinh: date | None
    gioi_tinh: Gender | None
    noi_sinh: str | None
    noi_dang_ky_khai_sinh: str | None
    que_quan: str | None
    dan_toc: str | None
    ton_giao: str | None
    quoc_tich: str | None
    nhom_mau: str | None
    noi_thuong_tru: str | None
    noi_tam_tru: str | None
    noi_o_hien_tai: str | None
    tinh_trang_cu_tru: ResidenceStatus | None
    ma_ho: str | None
    quan_he_voi_chu_ho: str | None
    so_dinh_danh_chu_ho: str | None
    tinh_trang_hon_nhan: MaritalStatus | None
    nghe_nghiep: str | None
    tinh_trang_song: LifeStatus | None
    ngay_mat: date | str |None
    so_dien_thoai: str | None
    email: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
