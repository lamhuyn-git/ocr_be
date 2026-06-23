"""Test cổng tầng 1: check_registered_user trả (hard, soft)."""
from __future__ import annotations

from datetime import date

import pytest

from app.services.form_workflow import check_registered_user
from conftest import gender, make_citizen, make_db, make_tamtru

FORM_ID = "11111111-1111-1111-1111-111111111111"


@pytest.mark.asyncio
async def test_missing_cccd_is_hard_fail():
    db = make_db(make_tamtru(registered_user_cccd=None))
    hard, soft = await check_registered_user(db, FORM_ID)
    assert hard == ["registered_user_missing"]
    assert soft == []


@pytest.mark.asyncio
async def test_no_tamtru_passes():
    db = make_db(None)
    hard, soft = await check_registered_user(db, FORM_ID)
    assert hard == [] and soft == []


@pytest.mark.asyncio
async def test_citizen_not_found_is_hard_fail():
    tamtru = make_tamtru(registered_user_cccd="001234567890", registered_user_name="Nguyen Van A")
    db = make_db(tamtru, None)  # tamtru tìm thấy, citizen None
    hard, soft = await check_registered_user(db, FORM_ID)
    assert hard == ["registered_user_not_found"]
    assert soft == []


@pytest.mark.asyncio
async def test_name_hard_phone_soft_split():
    tamtru = make_tamtru(
        registered_user_cccd="001234567890",
        registered_user_name="Tran Thi B",
        registered_user_phone="0900000000",
    )
    citizen = make_citizen(
        so_dinh_danh="001234567890",
        ho_chu_dem_va_ten="Nguyen Van A",   # khác hẳn → name hard
        so_dien_thoai="0911111111",         # khác → phone soft
    )
    db = make_db(tamtru, citizen)
    hard, soft = await check_registered_user(db, FORM_ID)
    assert "registered_user_name" in hard
    assert "registered_user_phone" in soft
    assert "registered_user_phone" not in hard


@pytest.mark.asyncio
async def test_only_soft_mismatch_does_not_block():
    tamtru = make_tamtru(
        registered_user_cccd="001234567890",
        registered_user_name="Nguyen Van A",
        registered_user_birth=date(1990, 1, 1),
        registered_user_gender="nam",
        registered_user_phone="0900000000",
        registered_user_mail="old@example.com",
    )
    citizen = make_citizen(
        so_dinh_danh="001234567890",
        ho_chu_dem_va_ten="Nguyen Van A",
        ngay_sinh=date(1990, 1, 1),
        gioi_tinh=gender("nam"),
        so_dien_thoai="0911111111",        # lệch (mềm)
        email="new@example.com",           # lệch (mềm)
    )
    db = make_db(tamtru, citizen)
    hard, soft = await check_registered_user(db, FORM_ID)
    assert hard == []
    assert set(soft) == {"registered_user_phone", "registered_user_mail"}


@pytest.mark.asyncio
async def test_birth_and_gender_mismatch_are_hard():
    tamtru = make_tamtru(
        registered_user_cccd="001234567890",
        registered_user_name="Nguyen Van A",
        registered_user_birth=date(1985, 5, 5),
        registered_user_gender="nu",
    )
    citizen = make_citizen(
        so_dinh_danh="001234567890",
        ho_chu_dem_va_ten="Nguyen Van A",
        ngay_sinh=date(1990, 1, 1),
        gioi_tinh=gender("nam"),
    )
    db = make_db(tamtru, citizen)
    hard, soft = await check_registered_user(db, FORM_ID)
    assert "registered_user_birth" in hard
    assert "registered_user_gender" in hard
    assert soft == []
