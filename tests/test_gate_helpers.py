"""Test helper thuần: _build_review_note (map mã lỗi) và _ocr_text (đọc field OCR)."""
from __future__ import annotations

from app.services.form_workflow import _build_review_note, _ocr_text
from app.services.extraction_error_catalog import EXTRACTION_ERROR_CATALOG, ErrorCode
from conftest import ocr_result


def test_build_review_note_maps_known_codes():
    # Assert theo message trong catalog (single-source) → bền với thay đổi wording.
    codes = [ErrorCode.registered_user_missing, ErrorCode.location_not_in_ward]
    note = _build_review_note(codes)
    for c in codes:
        assert EXTRACTION_ERROR_CATALOG[c].message in note
    assert "; " in note


def test_build_review_note_passthrough_unknown_code():
    assert _build_review_note(["some_unknown"]) == "some_unknown"


def test_ocr_text_reads_dict_field():
    result = ocr_result(ho_chu_dem_va_ten="Nguyen Van A")
    assert _ocr_text(result, "ho_chu_dem_va_ten") == "Nguyen Van A"


def test_ocr_text_missing_field_returns_empty():
    assert _ocr_text({"extracted_fields": {}}, "khong_co") == ""
    assert _ocr_text({}, "khong_co") == ""
