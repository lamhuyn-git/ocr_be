---
title: "Admin review flow: field-confirm + status-transition endpoints"
description: ""
status: pending
priority: P2
branch: "main"
tags: []
blockedBy: []
blocks: []
created: "2026-06-19T07:11:44.244Z"
createdBy: "ck:plan"
source: skill
---

# Admin review flow: field-confirm + status-transition endpoints

## Overview

Wire up the **human-in-the-loop review** that the data model + validation already
prepare for but no endpoint exposes. Today OCR runs, fields get a `pass /
need_review / invalid` verdict vs CSDL, and the form lands in `extracted`. Opening
the detail auto-moves it to `under_review` — and then the officer is stuck: there
is **no endpoint** to confirm a field or to move the form forward, even though
`FormResultConfirmRequest`, `FormTransitionRequest` and `assert_can_transition()`
all exist unused.

**Core policy this plan enforces** (per user decision): the officer corrects OCR
*misreads only*. `final_value` means "the correct reading of what is physically on
the CT01 paper" — never "the value we wish it were". When the form genuinely
deviates from the registration record (CSDL), the field stays `invalid`, the form
goes `invalid → require_adjust`, and it is returned to the citizen to re-submit.
The officer **cannot** rewrite content to force-approve. This is enforced by an
**approval gate**: a form cannot reach `valid` while any field is still
`need_review` or `invalid`.

`raw_value` is the OCR audit record and is left untouched by both new endpoints
(the existing generic `PATCH /form-results/{id}` is unchanged — locking it down is
an explicit out-of-scope follow-up, see Open Questions).

## Answer to the originating question

> "Form CT01 đúng với đăng ký thì không sao; nếu form lệch hoàn toàn thì admin có
> được chỉnh sửa không?"

- **Khớp / lệch nhỏ / OCR đọc sai** → officer confirms the field, editing
  `final_value` to the correct paper reading. Field → `valid`.
- **Lệch hoàn toàn về nội dung** (paper ≠ CSDL, đọc rõ ràng) → field stays
  `invalid`; officer **does not** overwrite it. The form is transitioned
  `reviewed → invalid → require_adjust` with a `review_note`, and bounced back to
  the citizen. The approval gate makes silently forcing `valid` impossible.

## Scope

- IN: per-field confirm endpoint; form status-transition endpoint; approval gate.
- OUT (deferred): CSDL write-back on `valid`; citizen notification on
  `returned`/`require_adjust`; locking `raw_value` in the generic PATCH.

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [Field confirm endpoint](./phase-01-field-confirm-endpoint.md) | Pending |
| 2 | [Form transition + approval gating](./phase-02-form-transition-approval-gating.md) | Pending |
| 3 | [Tests](./phase-03-tests.md) | Pending |

## Key dependencies

- Builds on the committed reextract work and the existing `ALLOWED_TRANSITIONS`
  state machine in `app/services/form_workflow.py`.
- No cross-plan blocking: `plans/260619-0253-reextract-endpoint` is already
  implemented; this plan consumes its state machine without modifying it.

## Open questions

- Locking `raw_value` against edits in `PATCH /form-results/{id}` directly follows
  from the chosen edit policy but was left out of scope. Revisit as a follow-up.
