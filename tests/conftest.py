"""Fixtures dùng chung cho test cổng kiểm tra hồ sơ tạm trú.

Các hàm cổng (check_registered_user / check_same_person) chỉ đọc DB qua
`db.execute(...).scalar_one_or_none()`. Test mock lớp biên này để kiểm tra
LOGIC quyết định, không cần dựng Postgres thật.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


def make_db(*scalar_results):
    """Tạo AsyncSession giả: mỗi lần `await db.execute(...)` rồi `.scalar_one_or_none()`
    trả lần lượt từng giá trị trong `scalar_results`."""
    results = []
    for r in scalar_results:
        res = MagicMock()
        res.scalar_one_or_none.return_value = r
        results.append(res)
    db = MagicMock()
    db.execute = AsyncMock(side_effect=results)
    return db


def make_tamtru(**kw) -> SimpleNamespace:
    base = dict(
        registered_user_cccd=None,
        registered_user_name=None,
        registered_user_birth=None,
        registered_user_gender=None,
        registered_user_phone=None,
        registered_user_mail=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def make_citizen(**kw) -> SimpleNamespace:
    base = dict(
        so_dinh_danh=None,
        ho_chu_dem_va_ten=None,
        ngay_sinh=None,
        gioi_tinh=None,
        so_dien_thoai=None,
        email=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def gender(value: str) -> SimpleNamespace:
    """Giả enum giới tính (Citizen.gioi_tinh.value)."""
    return SimpleNamespace(value=value)


def ocr_result(**fields) -> dict:
    """Bọc các field thành cấu trúc pipeline: {extracted_fields: {label: {text}}}."""
    return {"extracted_fields": {k: {"text": v} for k, v in fields.items()}}
