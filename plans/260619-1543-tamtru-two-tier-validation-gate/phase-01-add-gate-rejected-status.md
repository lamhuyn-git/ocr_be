---
phase: 1
title: Add gate_rejected status
status: completed
priority: P1
effort: 1h
dependencies: []
---

# Phase 1: Add gate_rejected status

## Overview
Thêm giá trị `gate_rejected` vào enum `FormStatus` (model + Postgres) để phân biệt "hồ sơ bị
chặn ở cổng tầng 1 (chưa/không dùng OCR)" với `extracted` ("OCR xong, chờ cán bộ soát").

## Requirements
- Functional: `FormStatus.gate_rejected` tồn tại ở cả Python enum lẫn kiểu enum `formstatus` trong DB.
- Non-functional: migration forward-only, an toàn với asyncpg (dùng pattern recreate-enum đã có).

## Architecture
- `Form.status = Column(Enum(FormStatus))` → native PG enum `formstatus`
  ([app/models/form.py:73](../../app/models/form.py)). Thêm value phải qua Alembic.
- Theo precedent [020_add_form_status_draft.py](../../alembic/versions/020_add_form_status_draft.py)
  và [021_update_formstatus_workflow.py](../../alembic/versions/021_update_formstatus_workflow.py):
  KHÔNG dùng `ALTER TYPE ... ADD VALUE` (lỗi trong transaction asyncpg) → **recreate enum**:
  drop default → tạo `formstatus_new` → đổi cột → drop cũ → rename → set lại default.
- Migration head hiện tại = `030`. Migration mới = `031`, `down_revision = "030"`.

## Related Code Files
- Modify: `app/models/form.py` — thêm `gate_rejected = "gate_rejected"` vào `FormStatus` (sau `overdue`).
- Create: `alembic/versions/031_add_form_status_gate_rejected.py`

## Implementation Steps
1. **Model:** trong `class FormStatus` ([form.py:13](../../app/models/form.py)) thêm dòng:
   ```python
   gate_rejected  = "gate_rejected"   # Bị chặn ở cổng kiểm tra (định danh/địa chỉ/sai người) — chưa cần OCR
   ```
2. **Migration 031:** copy cấu trúc của 021. `_VALUES` = 12 giá trị hiện tại + `'gate_rejected'`:
   ```python
   _VALUES = (
       "'draft','submitted','processing','extracted','under_review','reviewed',"
       "'valid','invalid','returned','require_adjust','failed','overdue','gate_rejected'"
   )
   ```
   `upgrade()`: DROP DEFAULT → CREATE TYPE formstatus_new → ALTER COLUMN ... USING status::text::formstatus_new
   → DROP TYPE formstatus → RENAME formstatus_new → SET DEFAULT 'submitted'.
   `downgrade()`: `raise NotImplementedError("forward-only: added 'gate_rejected' to formstatus")`.
3. Chạy `alembic upgrade head` trên DB dev, xác nhận không lỗi.

## Success Criteria
- [ ] `FormStatus.gate_rejected` import được trong Python.
- [ ] `alembic upgrade head` chạy sạch; `\dT+ formstatus` trong psql liệt kê `gate_rejected`.
- [ ] `alembic downgrade` của 031 báo NotImplementedError (đúng thiết kế forward-only).

## Risk Assessment
- **Recreate enum khóa bảng `forms` ngắn** khi ALTER COLUMN TYPE. Chấp nhận được (bảng nhỏ, môi trường nội bộ).
- **Quên remap giá trị cũ** → mọi status hiện có vẫn nằm trong `_VALUES` nên `USING status::text::...` an toàn.
- Nếu plan `admin-review-confirm-transition` cũng thêm migration enum → **chỉ một bên được là head**;
  bên sau phải rebase `down_revision` cho đúng chuỗi. Kiểm tra `alembic heads` trước khi tạo.
