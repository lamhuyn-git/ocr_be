"""Test cổng tầng 1 (sau OCR): check_same_person — CCCD chính, tên phụ."""
from __future__ import annotations

import pytest

from app.services.form_workflow import check_same_person
from conftest import make_db, make_tamtru, ocr_result

FORM_ID = "22222222-2222-2222-2222-222222222222"


@pytest.mark.asyncio
async def test_cccd_match_is_same():
    tamtru = make_tamtru(registered_user_cccd="001234567890")
    result = ocr_result(so_dinh_dan_ca_nhan="001234567890", ho_chu_dem_va_ten="Nguyen Van A")
    ok, _ = await check_same_person(result, make_db(tamtru), FORM_ID)
    assert ok is True


@pytest.mark.asyncio
async def test_cccd_mismatch_is_not_same():
    tamtru = make_tamtru(registered_user_cccd="001234567890")
    result = ocr_result(so_dinh_dan_ca_nhan="009999999999", ho_chu_dem_va_ten="Nguyen Van A")
    ok, reason = await check_same_person(result, make_db(tamtru), FORM_ID)
    assert ok is False
    assert reason


@pytest.mark.asyncio
async def test_cccd_unreadable_name_match_falls_back_true():
    tamtru = make_tamtru(registered_user_cccd="001234567890", registered_user_name="Nguyen Van A")
    result = ocr_result(so_dinh_dan_ca_nhan="???", ho_chu_dem_va_ten="Nguyen Van A")
    ok, _ = await check_same_person(result, make_db(tamtru), FORM_ID)
    assert ok is True


@pytest.mark.asyncio
async def test_cccd_unreadable_name_mismatch_is_not_same():
    tamtru = make_tamtru(registered_user_cccd="001234567890", registered_user_name="Nguyen Van A")
    result = ocr_result(so_dinh_dan_ca_nhan="", ho_chu_dem_va_ten="Tran Thi B")
    ok, _ = await check_same_person(result, make_db(tamtru), FORM_ID)
    assert ok is False


@pytest.mark.asyncio
async def test_no_tamtru_does_not_block():
    result = ocr_result(so_dinh_dan_ca_nhan="001234567890")
    ok, _ = await check_same_person(result, make_db(None), FORM_ID)
    assert ok is True
