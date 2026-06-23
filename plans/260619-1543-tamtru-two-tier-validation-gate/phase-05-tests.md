---
phase: 5
title: Tests
status: completed
priority: P2
effort: 2.5h
dependencies:
  - 1
  - 2
  - 3
  - 4
---

# Phase 5: Tests

## Overview
Test các cổng tầng 1/tầng 2 và luồng `process_form_bg`. `pytest.ini` đã có `asyncio_mode = auto`,
`testpaths = tests` — nhưng thư mục `tests/` CHƯA tồn tại, cần tạo + conftest.

## Requirements
- Functional: unit test cho `check_registered_user`, `check_same_person`; integration test cho `process_form_bg`
  qua 4 nhánh kết quả (gate-fail tầng 1, soft-only pass, same-person fail, hợp lệ).
- Non-functional: dùng DB test thật (asyncpg) hoặc SQLite async tùy hạ tầng sẵn có; mock OCR pipeline
  (`run_form_pipeline`) và S3 (`s3_service.download_to_temp/upload_file`) để không gọi GPU/mạng.

## Architecture
- Tạo `tests/conftest.py`: fixture `db` (AsyncSession), seed `Citizen`/`Form`/`TamtruForm`/`OrgAddress` tối thiểu.
- Mock biên: `process_form_bg` gọi `run_form_pipeline` ([form_service](../../app/services/form_service.py)) và
  `s3_service` — patch bằng `monkeypatch`/`unittest.mock` để trả `result` OCR giả.
- Tên test mô tả kịch bản, KHÔNG mã phase/finding (vd `test_check_registered_user_missing_cccd`).

## Related Code Files
- Create: `tests/conftest.py`
- Create: `tests/test_registered_user_gate.py` — unit `check_registered_user`.
- Create: `tests/test_same_person_gate.py` — unit `check_same_person`.
- Create: `tests/test_process_form_bg_flow.py` — integration 4 nhánh.

## Implementation Steps
1. conftest: engine/session test, factory seed citizen (CCCD, ho_chu_dem_va_ten, ngay_sinh, gioi_tinh, sdt, email).
2. `test_registered_user_gate.py`:
   - missing cccd → `(["registered_user_missing"], [])`
   - cccd not found → `(["registered_user_not_found"], [])`
   - name mismatch + phone mismatch → name ∈ hard, phone ∈ soft
   - chỉ phone/email mismatch → `hard == []`
3. `test_same_person_gate.py`:
   - CT01 cccd == online → `(True, _)`
   - CT01 cccd != online → `(False, _)`
   - CT01 cccd rỗng + tên khớp → `(True, _)`; tên khác → `(False, _)`
4. `test_process_form_bg_flow.py` (patch OCR + S3):
   - tầng-1 hard fail → status `gate_rejected`, không có FormResult
   - soft-only → status `extracted`, review_note có ghi chú mềm, có FormResult
   - same-person fail → status `gate_rejected`, `compute_field_statuses` không được gọi
   - hợp lệ → status `extracted` + FormResult
5. Chạy `pytest -q`; fix tới khi xanh. KHÔNG dùng mock giả để pass — mock chỉ ở biên OCR/S3.

## Success Criteria
- [ ] `pytest -q` xanh toàn bộ.
- [ ] 4 nhánh `process_form_bg` đều có assertion status + side-effect (FormResult/ review_note).
- [ ] Không test nào phụ thuộc GPU/mạng/S3 thật.

## Risk Assessment
- **Chưa có hạ tầng test DB** → nếu dựng async Postgres test phức tạp, fallback SQLite async cho unit,
  giữ integration tối thiểu. Quyết định khi cook tùy CI hiện có.
- `process_form_bg` mở nhiều `AsyncSessionLocal()` riêng → test cần patch `AsyncSessionLocal` về session test,
  hoặc refactor nhẹ để inject. Ghi nhận khi cook (tránh refactor lớn ngoài scope).
