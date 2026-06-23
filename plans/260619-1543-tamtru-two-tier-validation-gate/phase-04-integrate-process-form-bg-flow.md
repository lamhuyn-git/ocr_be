---
phase: 4
title: Integrate process_form_bg flow
status: completed
priority: P1
effort: 2.5h
dependencies:
  - 1
  - 2
  - 3
---

# Phase 4: Integrate process_form_bg flow

## Overview
Nối tất cả vào `process_form_bg`: tầng-1 gom lỗi cứng từ 2 nhóm check → fail thì `gate_rejected`;
ghi chú mềm (phone/email) kèm theo nhưng không fail; sau OCR chạy cổng same-person → fail thì `gate_rejected`,
bỏ qua tầng 2; pass hết mới `compute_field_statuses` → `extracted`. Cập nhật các chỗ status liên quan.

## Requirements
- Functional:
  - Tầng 1 fail (hard) hoặc CCCD rỗng hoặc địa chỉ ngoài phường → `status = gate_rejected`, `review_note` mô tả,
    return (không OCR). Ghi chú mềm (phone/email) gộp vào `review_note` nếu có (kể cả khi pass — để cán bộ biết).
  - Same-person fail (sau OCR) → `status = gate_rejected`, `review_note`, KHÔNG gọi `compute_field_statuses`,
    KHÔNG lưu FormResult tầng 2. (Cân nhắc vẫn lưu raw OCR? — xem Open Questions.)
  - Pass hết → như hiện tại: `compute_field_statuses` → lưu FormResult → `extracted`.
- Non-functional: background set `gate_rejected` không qua `assert_can_transition` (đúng thiết kế).

## Architecture
- File: [app/services/form_workflow.py](../../app/services/form_workflow.py).
- **Pre-extract gate** ([:222-233](../../app/services/form_workflow.py)):
  ```python
  hard, soft = await check_registered_user(db, form_db_id)
  hard += await check_location_register(db, form_db_id)   # check_location_register vẫn trả list[str] cứng
  if hard:
      form.status = FormStatus.gate_rejected
      form.review_note = _build_review_note(hard + soft)   # gộp cả note mềm để cán bộ thấy
      ... return
  # pass: nếu có soft → vẫn nhớ để ghi review_note sau khi extracted (không bắt buộc)
  ```
- **Post-extract same-person gate:** đặt SAU khi pipeline xong + TRƯỚC `compute_field_statuses`
  ([:260-276](../../app/services/form_workflow.py)):
  ```python
  is_same, reason = await check_same_person(result, db, form.id)
  if not is_same:
      form.status = FormStatus.gate_rejected
      form.review_note = reason
      await db.commit(); return
  ```
- **`ALLOWED_TRANSITIONS`** ([:31](../../app/services/form_workflow.py)): KHÔNG thêm `gate_rejected` vào map
  (đó là map cho transition THỦ CÔNG). Background set trực tiếp `form.status = gate_rejected` — hợp lệ vì
  không gọi `assert_can_transition`. Ghi comment giải thích.
- **`NOT_OVERDUE_STATES`** ([:40](../../app/services/form_workflow.py)): cân nhắc thêm `gate_rejected`
  (hồ sơ đã bị chặn không nên bị quét thành overdue). → **Thêm** `gate_rejected` vào set này.
- **`MANUAL_REEXTRACT_STATES`** ([:327](../../app/services/form_workflow.py)): **thêm** `gate_rejected`
  để cán bộ kích hoạt lại sau khi người dân bổ sung/sửa dữ liệu online (chạy lại gate sẽ pass nếu đã sửa).
- **Detail endpoint auto-move** ([app/api/v1/routes/form.py:226](../../app/api/v1/routes/form.py)):
  hiện `if form.status == FormStatus.extracted: → under_review`. `gate_rejected` KHÔNG khớp điều kiện này
  nên KHÔNG tự nhảy `under_review` — đúng mong muốn. Không cần sửa, nhưng **xác nhận** trong review.
- **Schema:** `FormResponse.status: FormStatus` ([schemas/form/form.py:60](../../app/schemas/form/form.py)) dùng enum
  trực tiếp → tự có `gate_rejected`, KHÔNG cần sửa schema. List filter ([form.py:79](../../app/api/v1/routes/form.py))
  chỉ loại `draft` → hồ sơ `gate_rejected` vẫn hiện cho cán bộ (đúng).

## Related Code Files
- Modify: `app/services/form_workflow.py` — `process_form_bg`, `NOT_OVERDUE_STATES`, `MANUAL_REEXTRACT_STATES`.
- Verify (no edit expected): `app/api/v1/routes/form.py` (auto-move guard), `app/schemas/form/form.py`.

## Implementation Steps
1. Cập nhật caller pre-extract gate theo chữ ký mới `(hard, soft)` của P2 + `check_location_register` (cứng).
2. Set `gate_rejected` + `review_note` khi `hard` không rỗng; return không OCR.
3. Sau pipeline, trước `compute_field_statuses`, gọi `check_same_person` (P3); fail → `gate_rejected` + return.
4. Thêm `gate_rejected` vào `NOT_OVERDUE_STATES` và `MANUAL_REEXTRACT_STATES`.
5. Grep toàn repo `check_registered_user` đảm bảo không còn caller dùng chữ ký cũ.
6. Xác nhận detail endpoint không auto-move `gate_rejected`.

## Success Criteria
- [ ] Hồ sơ CCCD rỗng / không tồn tại / sai name-birth-gender / địa chỉ ngoài phường → `gate_rejected`, không có FormResult tầng 2.
- [ ] Hồ sơ chỉ lệch phone/email → vẫn OCR → `extracted`, `review_note` có ghi chú mềm.
- [ ] Hồ sơ CT01 khác người online → sau OCR thành `gate_rejected`, không chạy tầng 2.
- [ ] Hồ sơ hợp lệ → `extracted` + FormResult như cũ.
- [ ] `gate_rejected` không bị overdue-scan; cán bộ re-extract được.
- [ ] Mở detail hồ sơ `gate_rejected` KHÔNG tự nhảy `under_review`.

## Risk Assessment
- **Lưu/không lưu raw OCR khi same-person fail:** nếu không lưu, cán bộ không xem được CT01 đã đọc gì để đối chứng.
  Xem Open Questions.
- **Merge conflict** với plan review-confirm-transition trên `form_workflow.py` — phối hợp thứ tự merge.
- Background set status bỏ qua state machine: chỉ đúng cho cổng nền; KHÔNG mở cơ chế này cho endpoint thủ công.

## Open Questions
- Khi cổng same-person fail: có nên vẫn lưu FormResult raw (status để trống/need_review) để cán bộ đối chứng CT01,
  hay chỉ lưu `review_note`? (Đề xuất: lưu raw không verdict để minh bạch — chốt khi cook.)
