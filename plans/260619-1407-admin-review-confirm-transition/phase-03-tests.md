---
phase: 3
title: "Tests"
status: pending
effort: ""
---

# Phase 3: Tests

## Overview

Cover the two new endpoints and — most importantly — the **policy invariant**: a
form cannot be approved (`valid`) while a field deviates from CSDL, and the officer
can correct an OCR misread but cannot force-pass a genuine mismatch.

## Pre-requisite: test harness

`pytest.ini` declares `testpaths = tests`, `asyncio_mode = auto`, and the pytest
cache records a prior suite (`tests/test_ward_form_access.py`,
`test_validation_engine.py`, `test_form_recovery.py`, …) — but the `tests/`
directory is **not present in the working tree**. Before writing new tests:

1. Confirm whether `tests/` (and its `conftest.py` with the async client / DB /
   user-and-ward fixtures) can be restored from git history:
   `git log --all --oneline -- tests/` then `git checkout <rev> -- tests/`.
2. If unrecoverable, recreate a minimal `tests/conftest.py`: async `httpx`/ASGI
   client over `app.main:app`, a transactional test DB session override on
   `get_db`, and fixtures producing a ward + a ward-officer + a citizen with a CCCD
   in `citizens`. Mirror the access patterns in `assert_form_ward_access`.

Do **not** invent a parallel harness if the original is restorable — reuse it.

## Requirements

- New file: `tests/test_admin_review_flow.py`.
- Tests run green under `pytest` with no skips/xfails masking real failures.

## Test cases

Field confirm (Phase 1):
1. `test_confirm_field_with_final_value` — POST confirm with `final_value` sets it,
   `confirmed_by == officer.id`, `status == valid`.
2. `test_confirm_field_defaults_to_suggested` — omit `final_value` →
   `final_value == suggested_value`; and when `suggested_value` is null →
   `final_value == raw_value`.
3. `test_confirm_field_requires_under_review` — confirm on a form in `extracted`
   (or `reviewed`) → 409.
4. `test_confirm_field_ward_isolation` — officer of another ward → 403.

Transition + approval gate (Phase 2):
5. `test_transition_illegal_move_rejected` — e.g. `under_review → returned` → 400/409.
6. `test_approval_gate_blocks_valid_with_pending_fields` — form in `reviewed` with a
   `need_review` or `invalid` field, transition to `valid` → 409.
7. `test_approval_gate_allows_valid_when_all_confirmed` — confirm every field
   (`valid`), then `reviewed → valid` succeeds.
8. `test_transition_note_persisted_on_invalid` — `reviewed → invalid` with a note →
   `form.review_note` set; then `invalid → require_adjust` succeeds.

End-to-end policy (the originating question):
9. `test_deviating_form_cannot_be_force_approved` — a field whose OCR reads clearly
   but mismatches CSDL is `invalid`; officer cannot reach `valid` (gate 409); the
   form is instead driven `reviewed → invalid → require_adjust`. Asserts the
   officer never overwrote `raw_value`.

## Related Code Files

- Create: `tests/test_admin_review_flow.py` (+ restore/recreate `tests/conftest.py`).
- Read for context: restored `tests/test_ward_form_access.py` for fixture + client
  usage patterns.

## Implementation Steps

1. Restore or recreate the harness (see Pre-requisite).
2. Write `tests/test_admin_review_flow.py` with the 9 cases above.
3. Run `~/.claude/skills/.venv/bin/python3 -m pytest tests/test_admin_review_flow.py -q`
   — or the project venv: `.venv/bin/python -m pytest -q`.
4. Fix endpoint code (Phases 1-2) until green; never adjust a test to mask a real
   defect.

## Success Criteria

- [ ] Harness present (restored or recreated) and importable.
- [ ] All 9 cases pass; full `pytest` run stays green (no regressions in the
      restored suite).
- [ ] `test_deviating_form_cannot_be_force_approved` proves the no-force-approve
      policy and `raw_value` immutability.

## Risk Assessment

- **Harness loss**: biggest unknown is whether `conftest.py` is recoverable. If
  recreation is needed, budget extra effort — flagged in plan Open Questions.
- **DB-backed gate test**: case 6/7 need real `FormResult` rows with distinct
  statuses; use the fixture DB session, not mocks, so the `func.count()` query is
  actually exercised.
