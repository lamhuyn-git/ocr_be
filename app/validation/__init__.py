"""
validation — đối chiếu kết quả trích xuất OCR với CSDL THẬT (Postgres) → trạng thái field.

Trạng thái field (decision.py): "pass" | "need_review" | "error", ánh xạ sang
FormResultStatus: valid | need_review | invalid.

Public API:
  from app.validation import compute_field_statuses
  statuses = await compute_field_statuses(db, ocr_fields, form_id)   # {label: FormResultStatus}

Lõi quyết định: status = f(confidence OCR, distance(OCR, giá trị thật CSDL)). KHÔNG ghi đè giá trị.
"""
from .decision import PASS, REVIEW, ERROR, Verdict  # noqa: F401
from . import field_rules  # noqa: F401
from .db_adapter import (  # noqa: F401
    DbCsdl, compute_field_statuses, verdict_to_status,
)
