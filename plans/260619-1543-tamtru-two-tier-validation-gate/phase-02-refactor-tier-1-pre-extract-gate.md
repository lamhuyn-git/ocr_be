---
phase: 2
title: Refactor tier-1 pre-extract gate
status: completed
priority: P1
effort: 2h
dependencies:
  - 1
---

# Phase 2: Refactor tier-1 pre-extract gate

## Overview
Sửa hàm `check_registered_user` để (a) coi CCCD khai online rỗng là **gate-fail**, và
(b) tách rõ field **cứng** (name/birth/gender → fail) khỏi field **mềm** (phone/email → chỉ ghi chú,
không fail). Giữ `check_location_register` nguyên hành vi. Hai nhóm vẫn **gom hết lỗi** (caller ở P4 quyết).

## Requirements
- Functional:
  - CCCD online rỗng/thiếu → trả mã lỗi cứng `registered_user_missing` (mới).
  - CCCD có nhưng không có trong `Citizen` → `registered_user_not_found` (giữ).
  - name/birth/gender lệch → mã lỗi cứng (giữ `registered_user_name/birth/gender`).
  - phone/email lệch → **KHÔNG** đưa vào list lỗi cứng; trả riêng dưới dạng cảnh báo mềm (ghi chú).
- Non-functional: hàm thuần (chỉ đọc DB + trả dữ liệu), không tự set status — status do P4 xử.

## Architecture
- File: [app/services/form_workflow.py](../../app/services/form_workflow.py).
- Hiện `check_registered_user` ([:147](../../app/services/form_workflow.py)) trả `list[str]` mã lỗi.
  Vì cần phân biệt lỗi-cứng vs cảnh-báo-mềm, đổi kiểu trả về thành:
  ```python
  # (hard_issues, soft_notes)
  tuple[list[str], list[str]]
  ```
  hoặc giữ `list[str]` cho lỗi cứng + tham số out cho soft. **Chọn tuple** cho rõ (KISS).
- `email` hiện chưa được so trong hàm này (chỉ phone). Online có `registered_user_mail`
  ([form.py:105](../../app/models/form.py)) và `Citizen.email`. Thêm so email **mềm**.
- Ngưỡng: name dùng `NAME_MATCH_DIST_MAX` (giữ). phone/email so bằng equality chuỗi (giữ phong cách hiện tại).
- `_ISSUE_NOTE` ([:43](../../app/services/form_workflow.py)) thêm dòng cho `registered_user_missing`
  và `registered_user_mail` (note mềm). Bổ sung ở P4 khi build review_note.

## Related Code Files
- Modify: `app/services/form_workflow.py` — `check_registered_user`, `_ISSUE_NOTE`.

## Implementation Steps
1. Đổi chữ ký: `async def check_registered_user(db, form_id) -> tuple[list[str], list[str]]:`
   trả `(hard, soft)`.
2. Đầu hàm: lấy `tamtru`. Nếu không có `tamtru` → `([], [])` (không phải hồ sơ tạm trú, để flow khác lo).
   Nếu có `tamtru` nhưng `registered_user_cccd` rỗng → `(["registered_user_missing"], [])` và return.
3. Lookup `Citizen` theo CCCD. Không thấy → `(["registered_user_not_found"], [])` (fail-fast nội bộ, khỏi so field).
4. So field cứng: name (fuzzy `NAME_MATCH_DIST_MAX`), birth (==), gender (lower ==) → append vào `hard`.
5. So field mềm: phone (==), email (lower ==) → nếu lệch append vào `soft` (mã `registered_user_phone`/`registered_user_mail`).
6. `return (hard, soft)`.
7. `_ISSUE_NOTE`: thêm `"registered_user_missing": "Chưa khai số định danh người thay đổi cư trú"`,
   `"registered_user_mail": "Email người đăng ký không khớp CSDL"`.

## Success Criteria
- [ ] CCCD rỗng → `hard == ["registered_user_missing"]`.
- [ ] CCCD không tồn tại → `hard == ["registered_user_not_found"]`, không so field.
- [ ] name lệch nhưng phone lệch → `hard` chứa name, `soft` chứa phone (form vẫn fail vì có hard).
- [ ] Chỉ phone/email lệch (name/birth/gender khớp) → `hard == []`, `soft` không rỗng → form KHÔNG fail cổng.

## Risk Assessment
- **Đổi chữ ký hàm** → mọi caller phải cập nhật. Caller duy nhất hiện tại: `process_form_bg`
  ([:224](../../app/services/form_workflow.py)) — sửa ở P4. Grep xác nhận không caller khác.
- gender so sánh: online lưu chuỗi tự do, `Citizen.gioi_tinh` là enum `.value`. Giữ logic `.lower()` hiện có,
  cẩn thận giá trị None (đã guard `if ... and citizen.gioi_tinh`).
