---
phase: 2
title: "Form transition + approval gating"
status: pending
effort: ""
---

# Phase 2: Form transition + approval gating

## Overview

Add the endpoint that moves a form through the review state machine
(`under_review → reviewed → valid/invalid → returned/require_adjust`) using the
existing `FormTransitionRequest` schema and `assert_can_transition()` helper, plus
the **approval gate** that encodes the core policy: a form cannot become `valid`
while any field is still `need_review` or `invalid`. This is what makes
force-approving a deviating CT01 impossible — the officer must either fix the OCR
(field → `valid` via Phase 1) or route the form to `invalid → require_adjust`.

## Requirements

- Functional:
  - `POST /form/transition?form_id=...`, body `FormTransitionRequest`
    (`to_status`, optional `note`).
  - Enforce `assert_can_transition(form, to_status)` (existing `ALLOWED_TRANSITIONS`).
  - **Approval gate**: when `to_status == valid`, reject (409) if any `FormResult`
    of the form has `status in {need_review, invalid}`.
  - Persist `note` into `form.review_note` when provided (primary use:
    `invalid` / `require_adjust` reasons shown to the citizen later).
  - Return the updated `FormResponse`.
- Non-functional:
  - `get_current_staff` + `assert_form_ward_access`, matching Phase 1 and reextract.

## Architecture

State machine already defined in `app/services/form_workflow.py`
(`ALLOWED_TRANSITIONS`, lines 31-38):

```
under_review → reviewed            (officer finished checking)
reviewed     → valid | invalid     (conclusion)   ← approval gate sits on `valid`
valid        → returned            (final: result delivered)
invalid      → require_adjust      (final: citizen must fix & re-submit)
```

`under_review` itself is reached automatically when the officer opens the detail
(`form.py:226`), so this endpoint covers everything from `reviewed` onward plus the
explicit `reviewed` step.

Gate query (only when targeting `valid`):
```python
blocking = (await db.execute(
    select(func.count()).select_from(FormResult).where(
        FormResult.form_id == form.id,
        FormResult.status.in_([FormResultStatus.need_review, FormResultStatus.invalid]),
    )
)).scalar_one()
if blocking:
    raise HTTPException(409, detail=f"Còn {blocking} trường chưa được chốt — không thể duyệt hợp lệ")
```

## Related Code Files

- Create: none.
- Modify:
  - `app/api/v1/routes/form.py` — add the `/transition` route (schema +
    `assert_can_transition` are already imported at lines 27-35).
- Read for context:
  - `app/services/form_workflow.py` — `assert_can_transition`, `ALLOWED_TRANSITIONS`.
  - `app/schemas/form/form.py` — `FormTransitionRequest` (exists, line 42).

## Implementation Steps

1. Ensure `func` (from `sqlalchemy`) and `FormResultStatus` are importable in
   `form.py` (add to existing imports).
2. Add route after `get_detail_forms_by_id`:
   ```python
   @router.post("/transition", response_model=FormResponse,
                summary="Officer transitions a form through the review state machine")
   async def transition_form(
       form_id: UUID,
       body: FormTransitionRequest,
       current_user: User = Depends(get_current_staff),
       db: AsyncSession = Depends(get_db),
   ):
       form = await db.get(FormModel, form_id)
       if not form:
           raise HTTPException(404, "Form not found")
       await assert_form_ward_access(form, current_user, db)
       wf.assert_can_transition(form, body.to_status)        # raises 400/409 on illegal move
       if body.to_status == FormStatus.valid:
           blocking = (await db.execute(
               select(func.count()).select_from(FormResult).where(
                   FormResult.form_id == form.id,
                   FormResult.status.in_([FormResultStatus.need_review, FormResultStatus.invalid]),
               )
           )).scalar_one()
           if blocking:
               raise HTTPException(status.HTTP_409_CONFLICT,
                   detail=f"Còn {blocking} trường chưa được chốt — không thể duyệt hợp lệ")
       form.status = body.to_status
       if body.note is not None:
           form.review_note = body.note
       await db.commit()
       await db.refresh(form)
       return form
   ```
3. Import check (`python -c "import app.main"`).

## Success Criteria

- [ ] Legal transitions succeed; illegal ones return 400/409 via
      `assert_can_transition`.
- [ ] `reviewed → valid` is blocked (409) while any field is `need_review`/`invalid`.
- [ ] `reviewed → valid` succeeds once all fields are `valid`.
- [ ] `note` is persisted to `review_note` on `invalid` / `require_adjust`.
- [ ] 403 for staff outside the form's ward; app imports cleanly.

## Risk Assessment

- **Gate scope**: counts ALL `FormResult` rows for the form. Correct here — every
  extracted field must be officer-vouched before `valid`. If a future template
  produces purely-informational fields, revisit (out of scope now).
- **`under_review → reviewed` with unconfirmed fields**: allowed by design — the
  gate is on `valid`, not `reviewed`, so the officer can step through `reviewed`
  and then choose `valid` vs `invalid`.

## Security Considerations

- Ward isolation via `assert_form_ward_access`; superadmin bypasses.
- State machine prevents skipping conclusion steps (e.g. `under_review → returned`).
