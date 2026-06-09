---
phase: 1
title: Models & Enums
status: completed
priority: P1
effort: 4h
dependencies: []
---

# Phase 1: Models & Enums

## Overview
Cập nhật SQLAlchemy models: đổi enum `OrgRole`, mở rộng `FormStatus`, thêm 5 cột review/result vào `Form`, thêm model mới `FormStatusHistory`. Đây là nguồn sự thật cho migration ở Phase 2.

## Requirements
- Functional: model phản ánh đúng vai trò + vòng đời form + lịch sử.
- Non-functional: giữ file <200 LOC; không tham chiếu plan/finding trong comment.

## Architecture
- `OrgRole`: `ward_admin`, `ward_officer` (bỏ owner/admin/member).
- `FormStatus`: `submitted, processing, extracted, under_review, approved, rejected, returned, failed`.
- `Form` thêm: `reviewed_by` (FK users SET NULL), `reviewed_at`, `review_note` (Text), `result_message` (Text), `result_file_path` (String 512).
- `FormStatusHistory`: `id`, `form_id` (FK forms CASCADE, index), `from_status` (Enum nullable), `to_status` (Enum), `actor_user_id` (FK users SET NULL), `note` (Text), `created_at`.

## Related Code Files
- Modify: `app/models/organization.py` (enum `OrgRole`).
- Modify: `app/models/form.py` (FormStatus, Form cột mới, FormStatusHistory model + relationship `forms.history`).
- Modify: `app/models/__init__.py` (export model mới nếu cần cho alembic autogen/metadata).

## Implementation Steps
1. `organization.py`: đổi `OrgRole` enum members → `ward_admin`, `ward_officer`. Đổi `default` của `OrganizationMember.role` → `ward_officer`.
2. `form.py`: mở rộng `FormStatus` (giữ `pending`? — bỏ, thay bằng `submitted`; xác nhận open-question #2). Thêm 5 cột vào `Form`.
3. `form.py`: thêm class `FormStatusHistory(Base)` + `relationship` 2 chiều với `Form` (`Form.history = relationship(..., cascade, order_by created_at)`).
4. Đảm bảo `FormStatusHistory` được import trong metadata (qua `app/models/__init__.py`) để alembic thấy.
5. Compile check: `python -c "import app.models"` không lỗi.

## Success Criteria
- [ ] `OrgRole` chỉ còn ward_admin/ward_officer.
- [ ] `FormStatus` có đủ 8 trạng thái vòng đời.
- [ ] `Form` có 5 cột mới + relationship `history`.
- [ ] `FormStatusHistory` model tồn tại, import sạch, không lỗi compile.

## Risk Assessment
- Đổi enum members trong code không tự đổi DB → phải khớp Phase 2. Mitigations: viết Phase 2 ngay sau, dùng cùng tên value.
- Quan hệ circular import (Form ↔ history) → khai báo trong cùng `form.py`.

## Red Team Corrections (verified — bắt buộc)
- **[C1] Touchpoint bổ sung bắt buộc:** đổi `OrgRole` lan vào — `app/api/v1/routes/organizations.py` (owner/admin/member tại :32,58,71,87,100,113,143,157-159,170,183), `app/schemas/organization.py:41` (`role: OrgRole = OrgRole.member`), `app/core/deps.py:48` (`require_org_role`). Phải viết lại auth org-CRUD theo vai trò mới: quyết định **super_admin** (is_superuser) là người tạo/quản lý phường + gán cán bộ; `ward_admin` quản lý trong phường; bỏ phụ thuộc `owner`. KHÔNG được để call site tham chiếu member đã xoá → app AttributeError lúc import.
- **[C2] Touchpoint FormStatus call sites:** `app/api/v1/routes/form.py:61` (model default), `:256`,`:268` (`submit_form`), `:103` (`_process_form_bg` → `completed`). Map `pending→submitted`, `completed→extracted` TẤT CẢ nơi.
- **[C2] Compile check thật:** không chỉ `import app.models` — phải `python -c "import app.main"` (import toàn app) để bắt breakage ở routes.
- **[C2] Sequencing:** thay đổi enum (model) + migration + writers phải atomic (xem plan.md Dependencies). Cân nhắc gộp Phase 1+2+phần writers của Phase 3 vào 1 lần deploy.
