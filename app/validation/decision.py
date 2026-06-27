from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from .text_match import digits_only, norm_distance
from .thresholds import OCR_CONF_MIN, NEAR_DIST_MAX
from app.services.extraction_error_catalog import ErrorCode

PASS = "pass"
REVIEW = "need_review"
ERROR = "error"


@dataclass
class Verdict:
    status: str
    reason: str
    suggestion: str = None      # giá trị CSDL gợi ý (khi REVIEW do lệch)
    distance: float = None
    db_value: str = None
    ocr_value: str = None
    code: str = None            # mã tình huống (ErrorCode) — để tra message riêng theo trường


def decide_match(ocr_value: str, db_value: str, conf=None, distance=None, soft=False) -> Verdict:
    if distance is None:
        distance = norm_distance(ocr_value, db_value)
    # Soft fields (phone, email): không gợi ý giá trị CSDL vì có thể đã thay đổi hợp lệ.
    # OCR trống: không gợi ý vì không có gì để đối chiếu.
    hint = None if (soft or not ocr_value) else db_value
    if conf is not None and conf < OCR_CONF_MIN:
        return Verdict(REVIEW, "Hệ thống không chắc về kết quả", hint, distance, db_value, ocr_value, code=ErrorCode.low_confidence)
    if distance == 0:
        return Verdict(PASS, "khớp với CSDL", None, 0.0, db_value, ocr_value, code=ErrorCode.match_ok)
    if distance <= NEAR_DIST_MAX:
        return Verdict(REVIEW, "Có sự chênh lệch nhỏ so với CSDL", hint, distance, db_value, ocr_value, code=ErrorCode.minor_diff)
    return Verdict(REVIEW if soft else ERROR, "đọc rõ nhưng khác CSDL", hint, distance, db_value, ocr_value, code=ErrorCode.mismatch)


def not_found(ocr_value: str, what: str) -> Verdict:
    return Verdict(ERROR, f"không tìm thấy trong CSDL ({what})", None, None, None, ocr_value, code=ErrorCode.not_found_in_db)


def validate_number_format(ocr_value: str, kind: str) -> Verdict | None:
    s = digits_only(ocr_value)
    if kind == "cccd":
        if len(s) != 12:
            return Verdict(ERROR, f"CCCD phải 12 chữ số (đọc {len(s)})", None, None, None, ocr_value, code=ErrorCode.cccd_format)
    elif kind == "phone":
        if not (9 <= len(s) <= 11):
            return Verdict(ERROR, f"số điện thoại không hợp lệ ({len(s)} chữ số)", None, None, None, ocr_value, code=ErrorCode.phone_format)
    elif kind == "date":
        if not _valid_date(ocr_value):
            return Verdict(ERROR, "ngày tháng không hợp lệ", None, None, None, ocr_value, code=ErrorCode.date_format)
    return None


def _valid_date(s: str) -> bool:
    import re
    m = re.findall(r"\d+", s or "")
    if len(m) < 3:
        return False
    try:
        datetime.strptime(f"{int(m[0]):02d}/{int(m[1]):02d}/{int(m[2]):04d}", "%d/%m/%Y")
        return True
    except ValueError:
        return False


def worst(statuses) -> str:
    """Rollup nhóm: mức xấu nhất thắng."""
    order = {PASS: 0, REVIEW: 1, ERROR: 2}
    return max(statuses, key=lambda s: order.get(s, 0)) if statuses else PASS
