# Thiết kế CSDL — Hệ thống quản lý form 3 vai trò (phường)

**Date:** 2026-06-08 · **Stack:** FastAPI + SQLAlchemy(async) + PostgreSQL + Alembic
**Status:** Design approved (brainstorm) → ready for /ck:plan

## 1. Problem statement

Hệ thống có 3 loại người dùng:
- **Người dân (citizen):** đăng nhập, nộp form, xem tình trạng form của mình, nhận kết quả.
- **Cán bộ phường (ward officer):** xem/quản lý các form nộp về phường của mình.
- **Super_admin:** xem tất cả — danh sách phường, form theo phường, chi tiết form, lịch sử 1 form.

Câu hỏi: cần những bảng nào để quản lý hệ thống?

## 2. Hiện trạng codebase (scout)

Đã có sẵn (`app/models/`, `alembic/versions/`):
- `users` (cờ `is_superuser`), `refresh_tokens` — auth JWT.
- `organizations` + `organization_members` (enum `OrgRole`: owner/admin/member).
- `form_templates` (loại form, vd CT01, YAML), `forms` (org_id, created_by, status pending/processing/completed/failed, extracted/validated_fields).
- `ocr_jobs` — OCR generic, trùng lặp một phần với `forms` (legacy).

**3 khoảng trống** so với yêu cầu:
1. Không có mô hình vai trò domain (citizen vs cán bộ là ngầm định).
2. Không có **lịch sử form** (status transitions / ai / khi nào / ghi chú).
3. Không có luồng **duyệt → trả kết quả** cho người dân.
4. `list_forms` hiện chỉ "form của tôi HOẶC superuser xem hết" — **chưa có scoping theo phường cho cán bộ**.

## 3. Quyết định đã chốt (qua hỏi đáp)

| Vấn đề | Lựa chọn |
|---|---|
| Mô hình phường + vai trò | **Tái dùng** `organizations`=phường; cán bộ=`organization_members`; citizen=user không membership; super_admin=`is_superuser` |
| Form ↔ phường | Người dân **chọn phường lúc nộp** (`forms.org_id`) |
| Luồng duyệt | **Có**: duyệt → approve/reject → trả kết quả |
| Lịch sử form | **Status transitions + actor + thời gian + ghi chú** |
| Nơi lưu kết quả | **Cột trực tiếp trên `forms`** (1:1, KISS) — không tạo bảng riêng |

## 4. Thiết kế cuối — 7 bảng

### Giữ nguyên (3)
- **`users`** — citizen = `is_superuser=false` + không có membership; super_admin = `is_superuser=true`. Vai trò suy ra, **không thêm cột**.
- **`refresh_tokens`** — phiên đăng nhập.
- **`form_templates`** — loại form, super_admin upload YAML.

### Tái dùng + sửa (3)
- **`organizations`** = **phường**. *(tùy chọn)* thêm `code` (mã phường), `district`.
- **`organization_members`** = cán bộ ↔ phường. Đổi enum `OrgRole` `owner/admin/member` → **`ward_admin` / `ward_officer`**. Hỗ trợ nhiều cán bộ/phường, nhiều phường/cán bộ.
- **`forms`** — thêm cột + mở rộng status:
  ```
  reviewed_by      UUID FK users(id) SET NULL    -- cán bộ duyệt
  reviewed_at      timestamptz NULL
  review_note      Text NULL                     -- lý do (esp. reject)
  result_message   Text NULL                     -- nội dung trả người dân
  result_file_path String(512) NULL              -- file kết quả (optional)
  ```
  Lifecycle `FormStatus` mở rộng (mỗi bước → 1 dòng history):
  ```
  submitted → processing → extracted → under_review → approved │ rejected → returned
                         ↘ failed (OCR error)
  ```
  `org_id` (đã có) = **ward_id**, citizen set lúc nộp, phải validate tồn tại + đổi thành **required** cho submission của dân.

### Thêm mới (1)
- **`form_status_history`** — "lịch sử của 1 form":
  ```
  id            UUID PK
  form_id       UUID FK forms(id) ON DELETE CASCADE, index
  from_status   FormStatus NULL          -- null ở bước đầu
  to_status     FormStatus NOT NULL
  actor_user_id UUID FK users(id) SET NULL
  note          Text NULL
  created_at    timestamptz default now()
  ```
  Append-only, 1 dòng/lần chuyển trạng thái.

### Out-of-scope (đã loại)
- `notifications` — chọn phương án không thông báo; dân poll `GET /form/{id}`.
- `form_attachments` — chỉ cần khi kết quả nhiều file; hiện 1 file đủ.
- `ocr_jobs` — không động; quyết định deprecate sau.

## 5. Ánh xạ quyền truy cập (logic, không phải schema)

| Actor | Nhận diện | Xem được |
|---|---|---|
| Người dân | user, không membership, `is_superuser=false` | chỉ `forms.created_by == me` |
| Cán bộ phường | có `organization_members` row | `forms.org_id IN (ward ids của tôi)` — **cần thêm nhánh này vào `list_forms`** |
| Super_admin | `is_superuser=true` | tất cả: phường, form/phường, chi tiết, lịch sử |

## 6. Touchpoints triển khai (cho /ck:plan)

- `app/models/form.py` — thêm cột + mở rộng `FormStatus`; new model `FormStatusHistory`.
- `app/models/organization.py` — đổi enum `OrgRole`.
- `alembic/versions/004_*.py` — migration mới (cột forms + bảng history + đổi enum). Lưu ý migrate dữ liệu enum cũ.
- `app/api/v1/routes/form.py` — scoping theo phường cho `list_forms`; `get_form` cho cán bộ phường; endpoint duyệt/approve/reject/return; ghi `form_status_history`; `submit_form` bắt buộc + validate `org_id`.
- `app/core/deps.py` — dependency cán bộ phường (membership theo `org_id` của form).
- `app/schemas/form.py` — schema review/result + history.

## 7. Net change

1 bảng mới (`form_status_history`) · 5 cột mới trên `forms` · 1 đổi enum (`OrgRole`) · 1 mở rộng enum (`FormStatus`). Phần còn lại đã có sẵn.

## 8. Unresolved questions

- Đổi enum `OrgRole` ảnh hưởng dữ liệu membership hiện có → cần chiến lược migrate (remap owner→ward_admin, member→ward_officer?). Xác nhận mapping khi plan.
- `ocr_jobs` deprecate hay giữ song song? (ngoài phạm vi đợt này)
- Mã phường/quận (`code`, `district`) có cần ngay không, hay thêm sau?
