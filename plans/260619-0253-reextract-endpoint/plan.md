# Plan: Endpoint trích xuất lại form

## Trạng thái: TODO

## Mục tiêu
Cho phép staff/superadmin kích hoạt lại OCR pipeline cho một form đã tồn tại.

---

## Phân tích hiện trạng

### Đã có sẵn
- `dispatch_reextract(form, db, background_tasks)` — reset status → `submitted`, xoá results cũ (trong `process_form_bg`), dispatch OCR ngầm
- `resolve_extraction_inputs(form, db)` — tìm CT01 path + active template
- `RE_EXTRACTABLE_STATES = {failed, overdue, processing}` — chỉ dùng cho auto-recovery

### Cần thêm
1. Mở rộng `RE_EXTRACTABLE_STATES` cho manual trigger
2. Endpoint `POST /form/reextract`
3. Quyền: `get_current_staff` + `assert_form_ward_access`

---

## Phases

### Phase 1 — Mở rộng trạng thái cho phép
File: `app/services/form_workflow.py`

Thêm `MANUAL_REEXTRACT_STATES` riêng (không đụng auto-recovery):
```python
MANUAL_REEXTRACT_STATES: set[FormStatus] = {
    FormStatus.failed,
    FormStatus.overdue,
    FormStatus.extracted,
    FormStatus.under_review,
    FormStatus.reviewed,
}
# Không cho: draft, submitted, processing (đang chạy), valid/invalid/returned/require_adjust (đã có quyết định)
```

### Phase 2 — Endpoint
File: `app/api/v1/routes/form.py`

```
POST /form/reextract?form_id=<uuid>
Auth: get_current_staff
```

Logic:
1. Lấy form theo `form_id` → 404 nếu không có
2. `assert_form_ward_access` — kiểm tra quyền phường
3. Kiểm tra `form.status in MANUAL_REEXTRACT_STATES` → 409 nếu không hợp lệ
4. Gọi `dispatch_reextract(form, db, background_tasks)`
   - Nếu False (thiếu CT01 hoặc template) → 422 với message rõ ràng
5. `await db.commit()`
6. Trả về `FormResponse` với status mới (`submitted`)

### Response
```json
{ "form_id_db": "...", "status": "submitted" }
```
Dùng lại `FormCreateResponse`.

---

## Files cần sửa
- `app/services/form_workflow.py` — thêm `MANUAL_REEXTRACT_STATES`
- `app/api/v1/routes/form.py` — thêm endpoint

## Files không cần sửa
- Schema (dùng lại `FormCreateResponse`)
- Model (không thay đổi DB)
- Migration (không cần)

---

## Risks
- Form đang `processing` → không cho reextract thủ công (race condition với OCR đang chạy)
- Form ở `valid`/`invalid` → không cho (đã có quyết định cán bộ, không nên ghi đè)
