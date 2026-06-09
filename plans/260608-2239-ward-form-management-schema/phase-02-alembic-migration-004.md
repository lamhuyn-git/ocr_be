---
phase: 2
title: Alembic Migration 004
status: completed
priority: P1
effort: 3h
dependencies:
  - 1
---

# Phase 2: Alembic Migration 004

## Overview
Migration `004` đồng bộ DB với models Phase 1: tạo bảng `form_status_history`, thêm 5 cột vào `forms`, tái tạo enum `orgrole` + `formstatus` (kèm remap dữ liệu cũ), backfill 1 dòng history cho form hiện có.

## Requirements
- Functional: `alembic upgrade head` và `downgrade` chạy sạch trên DB có dữ liệu.
- Non-functional: tên file domain-slug (không số phase trong tên migration nội dung), idempotent guards.

## Architecture
PostgreSQL **không xóa được value enum đang dùng** → tái tạo type:
- `orgrole`: tạo `orgrole_new('ward_admin','ward_officer')` → `ALTER TABLE organization_members ALTER COLUMN role TYPE orgrole_new USING (CASE role WHEN 'owner' THEN 'ward_admin' WHEN 'admin' THEN 'ward_admin' ELSE 'ward_officer' END::orgrole_new)` → drop `orgrole` → rename `orgrole_new`→`orgrole`. Cập nhật server_default → `ward_officer`.
- `formstatus`: tương tự, map `completed`→`extracted` (open-question #2), giữ pending? (bỏ → map `pending`→`submitted`), thêm các value mới.
- `forms`: add 5 cột (reviewed_by FK, reviewed_at, review_note, result_message, result_file_path).
- `form_status_history`: create_table + index `ix_form_status_history_form_id`.

## Related Code Files
- Create: `alembic/versions/004_form_review_and_history.py` (revision="004", down_revision="003").

## Implementation Steps
1. `upgrade()`:
   a. Tái tạo enum `orgrole` với USING-cast remap (drop default trước khi alter, set lại sau).
   b. Tái tạo enum `formstatus` với USING-cast remap.
   c. `op.add_column` 5 cột vào `forms` (reviewed_by có FK users SET NULL).
   d. `op.create_table("form_status_history", ...)` + `create_index`.
   e. (tùy chọn) backfill: insert 1 dòng history `to_status=<status hiện tại>` cho mỗi form đang có.
2. `downgrade()`: drop bảng history → drop 5 cột → tái tạo enum cũ (remap ngược, lossy → ghi chú).
3. Test: `alembic upgrade head` rồi `alembic downgrade -1` trên DB seed mẫu.

## Success Criteria
- [ ] `alembic upgrade head` chạy sạch trên DB có sẵn data.
- [ ] `organization_members.role` còn đúng ward_admin/ward_officer sau migrate.
- [ ] `forms` có 5 cột mới; `form_status_history` tồn tại + index.
- [ ] `alembic downgrade -1` chạy không lỗi.

## Risk Assessment
- ALTER TYPE + USING-cast trong transaction: ổn với asyncpg/alembic; nhưng `ALTER TYPE ADD VALUE` thì KHÔNG chạy trong tx → vì vậy chọn cách tái tạo type (an toàn hơn).
- Remap lossy khi downgrade (giá trị mới không có ở enum cũ) → xem [H4].
- Mất default khi alter column → nhớ set lại server_default.

## Red Team Corrections (verified — bắt buộc)
- **[C3] Trình tự ĐẦY ĐỦ cho CẢ HAI enum (bỏ "tương tự"):**
  `formstatus`: (1) `DROP INDEX ix_forms_status`; (2) `ALTER TABLE forms ALTER COLUMN status DROP DEFAULT`; (3) tạo type `formstatus_new`; (4) `ALTER COLUMN status TYPE formstatus_new USING (...)`; (5) `DROP TYPE formstatus`; (6) `RENAME formstatus_new → formstatus`; (7) `ALTER COLUMN status SET DEFAULT 'submitted'`; (8) `CREATE INDEX ix_forms_status`.
  `orgrole`: tương tự nhưng KHÔNG có index; drop default `member` → alter → set default `ward_officer`.
  Lý do: `forms.status` có index `ix_forms_status` (003:66) + `server_default='pending'` (003:51) phụ thuộc type → `DROP TYPE` fail nếu không gỡ trước.
- **[C4] USING-cast liệt kê ĐỦ 4 source value, KHÔNG dùng ELSE:**
  `CASE status WHEN 'pending' THEN 'submitted' WHEN 'processing' THEN 'processing' WHEN 'completed' THEN 'extracted' WHEN 'failed' THEN 'failed' END::formstatus_new`. Default mới = `'submitted'` (giá trị tồn tại trong enum mới). Tránh collapse `processing`/`failed` sai.
  `orgrole`: `owner→ward_admin, admin→ward_admin, member→ward_officer` (liệt kê đủ, không ELSE).
- **[M2] Backfill BẮT BUỘC (không optional):** mỗi form hiện có → 1 dòng `form_status_history(from_status=NULL, to_status=<status đã remap>, actor_user_id=NULL, note='migrated')`. Ghi chú lock: enum-recreate rewrite cả bảng `forms` (ACCESS EXCLUSIVE) — với bảng lớn tách backfill ra migration/batch riêng; data hiện tại nhỏ nên 1 tx ổn.
- **[M3] Xác nhận (đã verify):** `forms.status`=`formstatus` (003:50), `ocr_jobs.status`=`jobstatus` (001:29) — type RIÊNG. Recreate `formstatus` KHÔNG đụng `ocr_jobs`. Migration không được DROP `jobstatus`.
- **[H4] Downgrade không round-trip:** giá trị mới (`under_review/approved/rejected/returned/submitted`) không có ở enum cũ. Chọn 1: (a) `downgrade()` `raise NotImplementedError("004 is forward-only: lossy status/role remap")` để ops không tin nhầm rollback sạch; hoặc (b) snapshot `status`/`role` gốc vào cột tạm trước upgrade để khôi phục đúng. Mặc định đề xuất (a). Success criterion: KHÔNG chấp nhận "downgrade chạy không lỗi" nếu nó âm thầm huỷ dữ liệu lifecycle.
