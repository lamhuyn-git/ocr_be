---
title: Ward Form Management DB Schema
description: >-
  DB schema cho hệ thống quản lý form 3 vai trò (người dân / cán bộ phường /
  super_admin): review flow + lịch sử form + scoping theo phường.
status: completed
priority: P2
branch: main
tags:
  - database
  - alembic
  - rbac
  - forms
blockedBy: []
blocks: []
created: '2026-06-08T15:49:51.908Z'
createdBy: 'ck:plan'
source: skill
---

# Ward Form Management DB Schema

## Overview

Triển khai thiết kế CSDL đã chốt ở brainstorm (`plans/reports/brainstorm-260608-2239-ward-form-management-schema-report.md`).

3 vai trò: **người dân** (nộp form, xem trạng thái, nhận kết quả) · **cán bộ phường** (xem/duyệt form của phường mình) · **super_admin** (xem tất cả + lịch sử).

Quyết định đã chốt: `organizations`=phường · cán bộ=`organization_members` · citizen=user không membership · super_admin=`is_superuser` · citizen chọn phường lúc nộp (`forms.org_id`) · luồng duyệt approve/reject/return · lịch sử = status transitions + actor + note · kết quả lưu cột trên `forms`.

**Net DB change:** +1 bảng (`form_status_history`), +5 cột trên `forms`, đổi enum `orgrole` (→ ward_admin/ward_officer), mở rộng enum `formstatus`.

**[Red Team — đã sửa]** Đổi 2 enum KHÔNG phải thay đổi cô lập: nó lan vào code hiện có. Touchpoint bắt buộc (đã verify file:line):
- `app/api/v1/routes/organizations.py` (owner/admin/member ở :32,58,71,87,100,113,143,157-159,170,183), `app/schemas/organization.py:41`, `app/core/deps.py:48` — phải viết lại auth org-CRUD theo vai trò mới (super_admin quản lý phường).
- `app/api/v1/routes/form.py:61,256,268,103` (`FormStatus.pending`/`completed`) + `_process_form_bg` — đổi cùng lúc.
- Code test chưa tồn tại (`tests/` trống, `pytest` không có trong requirements).

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [Models & Enums](./phase-01-models-enums.md) | Completed |
| 2 | [Alembic Migration 004](./phase-02-alembic-migration-004.md) | Completed |
| 3 | [API Scoping & Review Flow](./phase-03-api-scoping-review-flow.md) | Completed |
| 4 | [Tests](./phase-04-tests.md) | Completed |

## Key Constraints

- Stack: FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic + PostgreSQL. Code style: file <200 LOC, không tham chiếu plan trong comment/migration name.
- **Enum migration gotcha (PostgreSQL):** không xóa được value khỏi enum type đang dùng → đổi `orgrole` phải tạo type mới + `ALTER COLUMN ... USING` cast + drop type cũ. `formstatus` cũng nên tái tạo để downgrade sạch.
- Backward-compat: dữ liệu membership cũ (owner/admin/member) phải remap; form cũ (status completed) phải map sang giá trị mới.

## Dependencies

- Phase 2 phụ thuộc Phase 1 (model = nguồn sự thật cho migration).
- Phase 3 phụ thuộc Phase 1+2 (schema + DB sẵn sàng).
- Phase 4 phụ thuộc Phase 3.

**[Red Team] Ràng buộc thực thi ATOMIC:** đổi enum (Phase 1 model) + migration (Phase 2) + sửa writers (`submit_form`, `_process_form_bg`, organizations.py auth — Phase 3) PHẢI deploy cùng 1 lần. Không được merge/deploy Phase 1+2 trước khi Phase 3 sửa hết call site, nếu không submit/pipeline 500 và app không boot.

## Red Team Review

### Session — 2026-06-08
**Findings:** 12 (12 accepted) · **Severity:** 4 Critical, 4 High, 4 Medium
**Note:** Security Adversary reviewer bị chặn bởi safeguard nền tảng; concerns IDOR/authz được Failure-Mode + Assumption reviewers phủ.

| # | Finding | Sev | Disp | Applied |
|---|---------|-----|------|---------|
| C1 | OrgRole bỏ owner/admin/member làm hỏng organizations.py + schemas + deps (app không boot) | Critical | Accept | P1+P3 touchpoints |
| C2 | Đổi FormStatus.pending/completed hỏng submit+pipeline; phải atomic | Critical | Accept | P1 + Dependencies |
| C3 | Migration enum thiếu xử lý index/default phụ thuộc; viết rõ cho cả 2 enum | Critical | Accept | P2 |
| C4 | USING-cast thiếu nhánh processing/failed; default mới 'pending' invalid | Critical | Accept | P2 |
| H1 | Không có test harness (pytest vắng trong requirements) — P4 thiếu effort | High | Accept | P4 |
| H2 | Không có cách tạo cán bộ / không có endpoint list phường cho dân | High | Accept | P3 |
| H3 | _process_form_bg đua với review writes; cần lock/precondition | High | Accept | P3 |
| H4 | Downgrade huỷ dữ liệu âm thầm | High | Accept | P2 |
| M1 | org_id required = breaking; form NULL org_id vô hình với cán bộ | Med | Accept | P3 |
| M2 | Backfill không giới hạn dưới ACCESS EXCLUSIVE lock; phải mandatory | Med | Accept | P2 |
| M3 | Xác nhận formstatus vs jobstatus là type riêng | Med | Accept | P2 |
| M4 | API contract drift (status mở rộng 8 value) | Med | Accept | P3 |

## Open Questions (xác nhận khi cook)

1. Remap `orgrole`: `owner`→`ward_admin`, `admin`→`ward_admin`, `member`→`ward_officer`? (mặc định đề xuất vậy)
2. Map `formstatus.completed` cũ → `extracted` hay `returned`? (đề xuất `extracted`: OCR xong, chờ duyệt)
3. Thêm `organizations.code`/`district` ngay đợt này hay để sau? (đề xuất: để sau, YAGNI)
4. `ocr_jobs` giữ nguyên (ngoài phạm vi).
