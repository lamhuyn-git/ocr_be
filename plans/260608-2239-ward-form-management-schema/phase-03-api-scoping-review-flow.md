---
phase: 3
title: API Scoping & Review Flow
status: completed
priority: P1
effort: 5h
dependencies:
  - 1
  - 2
---

# Phase 3: API Scoping & Review Flow

## Overview
Cập nhật quyền truy cập theo 3 vai trò + endpoint duyệt/trả kết quả + ghi lịch sử. Đây là phần logic biến schema thành hành vi đúng cho người dân / cán bộ phường / super_admin.

## Requirements
- Functional:
  - Người dân: chỉ thấy form của mình; nộp form bắt buộc chọn phường hợp lệ.
  - Cán bộ phường: thấy/duyệt form thuộc phường mình (`org_id IN ward ids`).
  - Super_admin: thấy tất cả + lịch sử + danh sách phường.
  - Mỗi lần đổi trạng thái → ghi `form_status_history`.
- Non-functional: dependency tái dùng, file <200 LOC, không N+1.

## Architecture
- `deps.py`: thêm helper lấy `ward_ids` của user (`select org_id from organization_members where user_id=me`); dependency `require_ward_access(form)` cho cán bộ.
- `form.py list_forms`: 3 nhánh — superuser (all) / có membership (org_id IN ward_ids, + filter org_id optional) / citizen (created_by==me).
- `form.py get_form`: cho phép owner / cán bộ cùng phường / superuser.
- Endpoint mới: `POST /form/{id}/review` (under_review), `POST /form/{id}/decision` (approved|rejected + review_note), `POST /form/{id}/result` (result_message/result_file → returned). Mỗi cái set `reviewed_by/reviewed_at` + insert history.
- `submit_form`: `org_id` bắt buộc + validate tồn tại trong `organizations`; insert history `to_status=submitted`.
- Helper `record_status_change(db, form, to_status, actor, note)` dùng chung.

## Related Code Files
- Modify: `app/core/deps.py` (ward access helpers).
- Modify: `app/api/v1/routes/form.py` (scoping + endpoints duyệt/result).
- Modify: `app/schemas/form.py` (DecisionRequest, ResultRequest, FormStatusHistoryResponse, thêm cột review vào FormDetailResponse).
- Modify: `app/services/form_service.py` (pipeline set status `extracted` thay `completed`).
- **Modify (BẮT BUỘC):** `app/api/v1/routes/organizations.py` (rewrite auth org-CRUD off owner/admin/member; `GET /organizations` cho citizen; endpoint super_admin gán cán bộ), `app/schemas/organization.py` (default role). Xem Red Team Corrections [C1]/[H2].

## Implementation Steps
1. `deps.py`: `get_user_ward_ids(user, db)` + `require_form_ward_access`.
2. `schemas/form.py`: thêm request/response models + cột review vào detail; endpoint history list response.
3. `form.py`: refactor `list_forms` 3 nhánh; cập nhật `get_form` cho cán bộ; thêm helper `record_status_change`.
4. `form.py`: `submit_form` bắt buộc + validate `org_id`, ghi history `submitted`.
5. `form.py`: thêm 3 endpoint review/decision/result (guard `require_form_ward_access` hoặc superuser), mỗi cái ghi history.
6. `form.py`: endpoint `GET /form/{id}/history` (owner/cán bộ phường/superuser).
7. `form_service.py`/background task: khi OCR xong set `extracted` + ghi history (actor=None/system).
8. Compile + smoke test thủ công qua /docs.

## Success Criteria
- [ ] Citizen chỉ list/get được form của mình; nộp thiếu/ sai `org_id` → 422/404.
- [ ] Cán bộ phường list/get/duyệt được form đúng phường, bị chặn phường khác (403).
- [ ] Super_admin thấy tất cả + history.
- [ ] Mọi chuyển trạng thái tạo đúng 1 dòng `form_status_history`.

## Risk Assessment
- Rò rỉ chéo phường nếu nhánh scoping sai → test kỹ ở Phase 4 (negative cases).
- `org_id` cũ nullable trên form cũ → xem [M1].
- Đua ghi history khi pipeline + user thao tác đồng thời → xem [H3].

## Red Team Corrections (verified — bắt buộc)
- **[C1] Viết lại auth org-CRUD (organizations.py):** `invite_member` (organizations.py:109) hiện gated bởi `OrgRole.owner/admin` đã bị xoá → sau đổi enum KHÔNG ai tạo được cán bộ. Định nghĩa rõ: **super_admin (is_superuser)** gán cán bộ vào phường; `ward_admin` (tuỳ chọn) quản lý cán bộ trong phường. Rewrite mọi `require_org_role(...)` call site sang vai trò mới.
- **[H2] Endpoint bắt buộc (không optional):**
  - `GET /organizations` (list phường) **đọc được bởi citizen** (không cần membership) — để UI dân chọn phường lúc nộp. Hiện `list_my_organizations` (organizations.py:38) chỉ trả membership của caller → citizen rỗng.
  - Endpoint super_admin gán cán bộ↔phường (thay `invite_member` cũ).
- **[H3] Chống race với `_process_form_bg`:** endpoint review/decision/result phải `SELECT ... FOR UPDATE` form + kiểm tra precondition trạng thái hợp lệ (predecessor) trước khi chuyển; trả **409** nếu không khớp. `_process_form_bg` (form.py:79-83, session riêng, `expire_on_commit=False` database.py:16) chỉ được set `extracted` khi status vẫn là `processing` (không ghi đè khi đã `under_review`). Định nghĩa rõ quy tắc khi OCR xong lúc người đã duyệt.
- **[M1] Xử lý NULL org_id rõ ràng:** (1) form legacy `org_id IS NULL` vô hình với cán bộ (`org_id IN ward_ids` không khớp NULL) → quyết định: backfill ở Phase 2 / chỉ super_admin thấy / bucket riêng; (2) super_admin submit có cần ward? → miễn validate required cho super_admin hoặc bắt buộc chọn; (3) `org_id` required chỉ ở API layer (cột vẫn nullable) → ghi rõ đây là breaking change cho client cũ.
- **[M4] API contract drift:** `FormResponse.status` (schemas/form.py:39), `FormCreateResponse.status` (:65), `status_filter` (form.py:282) mở rộng 8 value — thay đổi additive; thêm kiểm tra response shape ở Phase 4. Cập nhật OpenAPI/tài liệu.
