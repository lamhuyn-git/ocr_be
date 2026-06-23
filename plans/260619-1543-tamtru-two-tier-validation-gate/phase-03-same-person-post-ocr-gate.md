---
phase: 3
title: Same-person post-OCR gate
status: completed
priority: P1
effort: 1.5h
dependencies: []
---

# Phase 3: Same-person post-OCR gate

## Overview
Thêm hàm kiểm tra **CT01 (giấy đã OCR) và form online có cùng một người không**, chạy SAU trích xuất
nhưng TRƯỚC `compute_field_statuses`. So **CCCD là chính** (mạnh), tên+phường chỉ phụ. Lệch → cổng fail.

## Requirements
- Functional: trả verdict same-person (`ok: bool` + lý do) từ kết quả OCR + dữ liệu online + phường.
  - So CCCD CT01 (OCR `so_dinh_dan_ca_nhan`, [field_rules.py:26](../../app/validation/field_rules.py))
    vs `registered_user_cccd` (online) bằng `digits_only` rồi `==`. Khớp → cùng người (đủ, return ok).
  - CCCD CT01 thiếu/sai định dạng → fallback so **tên** (fuzzy `NAME_MATCH_DIST_MAX`) **và** phường.
    Khớp cả hai → ok; ngược lại → fail.
- Non-functional: hàm thuần, không set status; nhận sẵn `result` (dict OCR) + `db` + `form_id`.

## Architecture
- File: thêm hàm trong [app/services/form_workflow.py](../../app/services/form_workflow.py) (cùng chỗ các check khác),
  hoặc tách `app/validation/same_person.py` nếu muốn gọn — **chọn để cùng form_workflow.py** (KISS, gần caller).
- Lấy giá trị OCR: dùng helper kiểu `_txt` trong [groups.py:19](../../app/validation/groups.py) — đọc
  `result["extracted_fields"][label]["text"]`. Trong form_workflow viết helper nhỏ tương đương (đừng import vòng).
- "Phường" của CT01: lấy từ OCR `kinh_gui` (Công an Phường X) hoặc địa chỉ; "phường" online: từ `OrgAddress`/`Form.org`.
  → **Đơn giản hóa:** dùng lại `check_location_register` logic (địa chỉ OCR `noi_dung_de_nghi` vs phường tiếp nhận)
  là KHÔNG đúng mục tiêu. Same-person fallback chỉ cần **tên** so tên; phường để loại trùng tên.
  Vì CCCD đã là khóa chính và hiếm khi thiếu, **fallback tên+phường là phụ** — giữ tối giản:
  so tên OCR `ho_chu_dem_va_ten` vs `registered_user_name` (online). Nếu cần phường, so phần phường trong
  địa chỉ online `location_register`. Ghi rõ giới hạn trong code comment.
- Trả về: `Verdict`-like đơn giản `tuple[bool, str]` = `(is_same, reason)`.

## Related Code Files
- Modify: `app/services/form_workflow.py` — thêm `check_same_person(result, db, form_id) -> tuple[bool, str]`.
- Read for context: `app/validation/groups.py`, `app/validation/field_rules.py`, `app/validation/text_match.py`.

## Implementation Steps
1. Helper đọc OCR text: `_ocr_text(result, label) -> str`.
2. Lấy `registered_user_cccd`, `registered_user_name`, `location_register` từ `TamtruForm` theo `form_id`.
3. CCCD CT01 = `digits_only(_ocr_text(result, FR.KEY_CCCD_NGUOI_DK))`. Nếu đủ 12 số:
   - `== digits_only(registered_user_cccd)` → `(True, "CCCD CT01 khớp người khai online")`.
   - khác → `(False, "CCCD trên CT01 khác người khai online")`.
4. CCCD CT01 thiếu/sai 12 số → fallback: `norm_distance(ten_ct01, registered_user_name) <= NAME_MATCH_DIST_MAX`
   (và nếu có phường, so phường). Khớp → `(True, ...)`; không → `(False, "Không xác định được CT01 cùng người khai online")`.
5. Return tuple.

## Success Criteria
- [ ] CCCD CT01 == online CCCD → `(True, ...)`.
- [ ] CCCD CT01 khác online → `(False, ...)`.
- [ ] CCCD CT01 rỗng nhưng tên khớp → `(True, ...)` (fallback).
- [ ] CCCD CT01 rỗng và tên khác → `(False, ...)`.

## Risk Assessment
- **Trùng lặp với tầng 2:** `validate_ho_thay_doi` ([groups.py:56](../../app/validation/groups.py)) cũng
  lookup citizen bằng CCCD OCR. Đây là hard-gate đặt TRƯỚC tầng 2 để dừng sớm + thông báo "sai người" rõ ràng;
  tầng 2 không chạy khi gate này fail nên không mâu thuẫn. Ghi rõ ranh giới trong comment.
- **Tên fallback yếu** (trùng tên/OCR sai dấu) — chỉ dùng khi CCCD CT01 không đọc được; chấp nhận, vì CCCD là chính.
- OCR field name phải đúng `so_dinh_dan_ca_nhan` (lưu ý: `field_rules.NUMBER_KIND` viết `so_dinh_dan_ca_nhan` —
  giữ đồng nhất với key thực tế OCR trả về).
