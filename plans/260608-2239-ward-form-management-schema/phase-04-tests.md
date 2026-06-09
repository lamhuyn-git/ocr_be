---
phase: 4
title: Tests
status: completed
priority: P2
effort: 6-8h
dependencies:
  - 3
---

# Phase 4: Tests

## Overview
Test tự động cho 3 vai trò scoping, luồng duyệt, và lịch sử form. Tập trung negative cases (rò rỉ chéo phường) vì đây là rủi ro bảo mật chính.

## Requirements
- Functional: cover citizen/officer/super_admin paths + review transitions + history rows.
- Non-functional: không mock OCR pipeline thật (stub `run_form_pipeline`); dùng DB test (transaction rollback per test).

## Architecture
- pytest + httpx AsyncClient + async session fixture (rollback). Fixtures: super_admin, 2 phường (A,B), cán bộ A, cán bộ B, citizen, form thuộc phường A.
- Stub pipeline để set `extracted` deterministic.

## Related Code Files
- Create: `tests/conftest.py` (nếu chưa có): app + db + auth-token fixtures.
- Create: `tests/test_form_scoping.py` (list/get theo vai trò).
- Create: `tests/test_form_review_flow.py` (review→decision→result + status transitions).
- Create: `tests/test_form_history.py` (mỗi transition tạo 1 dòng; GET /history quyền).

## Implementation Steps
1. Dựng fixtures auth (tạo user + membership + JWT) cho từng vai trò.
2. `test_form_scoping`: citizen chỉ thấy form mình; cán bộ A thấy form phường A, KHÔNG thấy phường B (403/404); super_admin thấy tất cả.
3. `test_form_review_flow`: submit (org_id bắt buộc/validate) → extracted → under_review → approved/rejected → returned; cán bộ phường khác bị 403.
4. `test_form_history`: đếm dòng history sau mỗi transition; quyền GET /history.
5. Chạy `pytest -q`, đảm bảo xanh; không bỏ qua test fail.

## Success Criteria
- [ ] Tất cả test xanh (`pytest`).
- [ ] Có negative test chặn truy cập chéo phường.
- [ ] History assert đúng số dòng + actor + to_status.

## Risk Assessment
- Thiếu hạ tầng test async hiện tại → xem [H1].
- Phụ thuộc DB Postgres test → dùng schema riêng / rollback; tránh đụng data dev.

## Red Team Corrections (verified — bắt buộc)
- **[H1] Test harness CHƯA TỒN TẠI — prerequisite cứng, không "nếu chưa có":** đã verify không có `tests/`, không `pytest.ini/pyproject/conftest`, `requirements.txt` không có `pytest`/`pytest-asyncio` (chỉ có `httpx`). Bước 0 bắt buộc trước mọi test:
  1. Thêm vào `requirements.txt`: `pytest`, `pytest-asyncio`, (DB test: `aiosqlite` hoặc dùng Postgres test riêng).
  2. Tạo `conftest.py`: event-loop, engine + session rollback-per-test, async client (httpx ASGITransport), fixtures JWT mint cho 4 actor (super_admin / ward_admin / ward_officer / citizen), stub `run_form_pipeline`.
  - **Re-estimate effort: ~6-8h** (không phải 3h) vì dựng hạ tầng từ đầu.
- **Ưu tiên negative test bảo mật:** cross-ward access (cán bộ A đọc form phường B → 403), citizen đọc form người khác → 403, precondition 409 cho race [H3], NULL org_id visibility [M1].
