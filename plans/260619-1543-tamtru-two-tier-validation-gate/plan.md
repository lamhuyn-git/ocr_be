---
title: 'Tamtru CT01: two-tier validation gate refactor'
description: ''
status: completed
priority: P2
branch: main
tags: []
blockedBy: []
blocks: []
created: '2026-06-19T08:54:24.336Z'
createdBy: 'ck:plan'
source: skill
---

# Tamtru CT01: two-tier validation gate refactor

## Overview

Làm rõ luồng kiểm tra hồ sơ tạm trú CT01 trong `process_form_bg`
([app/services/form_workflow.py:207](../../app/services/form_workflow.py)) thành **2 tầng** tường minh:

- **Tầng 1 — cổng (gate) trước/quanh trích xuất:** xác minh người đăng ký + địa chỉ
  *trước* khi tốn OCR; thêm cổng "cùng người" (CT01 vs online) *sau* trích xuất nhưng
  *trước* validate field. Bất kỳ cổng nào fail → hồ sơ vào trạng thái mới `gate_rejected`,
  KHÔNG chạy/không dùng validate field.
- **Tầng 2 — validate field:** `compute_field_statuses` như hiện tại, chỉ chạy khi tầng 1 pass.

Phần lớn xương sống đã tồn tại (pre-extract gate + `compute_field_statuses`). Plan này
**sửa các lỗ hổng logic đã chốt**, không viết lại từ đầu.

## Quyết định đã chốt (ràng buộc thiết kế)

1. **Khóa định danh = `registered_user_cccd`** (→ `Citizen.so_dinh_danh`, unique). KHÔNG có
   `registered_user_id`. So CCCD là thừa (nó là khóa lookup). Field so thật: `name/birth/gender`
   (CỨNG → fail cổng), `phone/email` (MỀM → chỉ ghi chú, KHÔNG fail).
2. **CCCD khai online rỗng/thiếu = gate-fail** ("cần bổ sung định danh"), không cho lọt vào OCR.
   (Hiện `check_registered_user` return `[]` = âm thầm pass — phải sửa.)
3. **Hai nhóm check tiền-trích-xuất độc lập (người đăng ký + địa chỉ) GOM HẾT lỗi báo 1 lần**
   (không short-circuit giữa 2 nhóm). Trong nhóm người đăng ký thì fail-fast nội bộ
   (không tồn tại → khỏi so field).
4. **Status mới `gate_rejected`** phân biệt "chặn ở cổng, chưa/không dùng OCR" với `extracted`
   ("OCR xong, chờ soát"). Background được set `gate_rejected` NGOÀI `ALLOWED_TRANSITIONS`
   (cổng chạy nền, không qua transition thủ công của cán bộ).
5. **Cổng "cùng người" hard-gate sau extraction, trước `compute_field_statuses`:** so CCCD trên
   CT01 (OCR `so_dinh_dan_ca_nhan`) vs `registered_user_cccd` (online) làm CHÍNH; tên+phường phụ.
   Lệch → `gate_rejected`, bỏ qua tầng 2.

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [Add gate_rejected status](./phase-01-add-gate-rejected-status.md) | Completed |
| 2 | [Refactor tier-1 pre-extract gate](./phase-02-refactor-tier-1-pre-extract-gate.md) | Completed |
| 3 | [Same-person post-OCR gate](./phase-03-same-person-post-ocr-gate.md) | Completed |
| 4 | [Integrate process_form_bg flow](./phase-04-integrate-process-form-bg-flow.md) | Completed |
| 5 | [Tests](./phase-05-tests.md) | Completed |

**Thứ tự phụ thuộc:** P1 (enum) → nền cho P4. P2, P3 là hàm thuần (trả list lỗi), độc lập P1.
P4 nối tất cả vào `process_form_bg` + status flow. P5 test toàn bộ. Khuyến nghị làm tuần tự P1→P5.

## Quy ước code (bắt buộc)

- Code comment & tên file/migration **KHÔNG** tham chiếu số phase/finding. Giải thích *lý do*
  (invariant, định danh, soft/hard) chứ không phải nguồn gốc plan.
- Migration đặt tên theo domain slug, ví dụ `031_add_form_status_gate_rejected.py`.

## Dependencies

- Cùng đụng `FormStatus` enum + `ALLOWED_TRANSITIONS`/`form_workflow.py` với plan
  `260619-1407-admin-review-confirm-transition` (review flow sau `extracted`). Không phụ thuộc
  output (hồ sơ `gate_rejected` không vào luồng review của plan kia), nhưng **chú ý merge**: cả hai
  sửa enum `formstatus` và file `form_workflow.py`. Không đặt `blockedBy` — chỉ cảnh báo conflict.
