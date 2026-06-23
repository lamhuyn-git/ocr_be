---
phase: 1
title: "Field confirm endpoint"
status: pending
effort: ""
---

# Phase 1: Field confirm endpoint

## Overview

Add an endpoint for the officer to **confirm one extracted field**: vouch for its
`final_value` (the correct reading of the paper), stamp `confirmed_by`, and set the
field's status to `valid`. This is the only field-level write that the review flow
needs; correcting an OCR misread and accepting a clean field are the same action,
differing only by whether `final_value` is supplied.

Marking a field `invalid` (genuine deviation) is **not** a separate field action —
the officer simply leaves it unconfirmed and decides at the form level (Phase 2).
This keeps the field surface to a single verb and pushes the substantive
accept/reject decision to the form transition, where the approval gate lives.

## Requirements

- Functional:
  - `POST /form-results/{result_id}/confirm`, body `FormResultConfirmRequest`
    (`final_value: str | None`).
  - `final_value` provided → set it verbatim (officer-corrected reading).
  - `final_value` omitted/null → accept the system value: `final_value =
    suggested_value or raw_value` (suggested is the CSDL hint; falls back to the
    raw OCR text when there is no hint, e.g. a `pass` field).
  - Always set `confirmed_by = current_user.id` and `status = valid`.
  - Re-confirming an already-confirmed field is allowed (idempotent overwrite).
- Non-functional:
  - Reuse `get_current_staff` + `assert_form_ward_access` (consistent with
    reextract). No new permission concept.
  - Only allowed while the parent form is `under_review` (the active review lock).

## Architecture

Field semantics (already in the model, `app/models/form.py:126`):

| column | meaning | who writes |
|--------|---------|-----------|
| `raw_value` | OCR reading of the paper | pipeline only — immutable here |
| `suggested_value` | CSDL ground-truth hint (null on `pass`) | pipeline |
| `final_value` | officer-confirmed correct reading | **this endpoint** |
| `confirmed_by` | officer user id | **this endpoint** |
| `status` | valid / need_review / invalid | this endpoint sets `valid` |

The endpoint needs the parent form (for ward-access + status gate), so it loads
`FormResult` then `Form` by `result.form_id`.

## Related Code Files

- Create: none.
- Modify:
  - `app/api/v1/routes/form_results.py` — add the `/confirm` route.
- Read for context:
  - `app/schemas/form/form_result.py` — `FormResultConfirmRequest` (exists, line 62).
  - `app/core/deps.py` — `get_current_staff`, `assert_form_ward_access`.
  - `app/models/form.py` — `FormResult`, `FormResultStatus`, `FormStatus`.

## Implementation Steps

1. In `form_results.py`, import `FormResultConfirmRequest`, `FormStatus`,
   `assert_form_ward_access`, and `get_current_staff` (already imported).
2. Add route:
   ```python
   @router.post("/{result_id}/confirm", response_model=FormResultResponse,
                summary="Officer confirms one field (vouch final_value)")
   async def confirm_form_result(
       result_id: UUID,
       body: FormResultConfirmRequest,
       current_user: User = Depends(get_current_staff),
       db: AsyncSession = Depends(get_db),
   ):
       result = await db.get(FormResult, result_id)
       if not result:
           raise HTTPException(404, "Form result not found")
       form = await db.get(FormModel, result.form_id)
       await assert_form_ward_access(form, current_user, db)
       if form.status != FormStatus.under_review:
           raise HTTPException(status.HTTP_409_CONFLICT,
               detail=f"Form phải ở 'under_review' để chốt field (hiện: {form.status.value})")
       result.final_value = (
           body.final_value if body.final_value is not None
           else (result.suggested_value or result.raw_value)
       )
       result.confirmed_by = current_user.id
       result.status = FormResultStatus.valid
       await db.flush()
       await db.refresh(result)
       return result
   ```
3. Verify the module imports `FormStatus` and `FormResultStatus` from
   `app.models.form` (currently only `Form`, `FormResult` are imported — add them).
4. Run `python -c "import app.main"` (or `uvicorn` import check) to confirm no
   import/compile errors.

## Success Criteria

- [ ] `POST /form-results/{id}/confirm` with `final_value` sets `final_value`,
      `confirmed_by`, `status=valid`.
- [ ] Omitting `final_value` falls back to `suggested_value or raw_value`.
- [ ] Returns 409 when the form is not `under_review`.
- [ ] Returns 403 for a staff member outside the form's ward.
- [ ] App imports cleanly (no syntax/import error).

## Risk Assessment

- **Race with reextract**: reextract resets the form to `submitted` and deletes
  `FormResult` rows. The `under_review` gate makes a confirm on a form being
  re-extracted impossible (reextract leaves `submitted`/`processing`). Low risk.
- **`raw_value` untouched**: confirm never writes `raw_value`, preserving the audit
  trail as the policy requires.

## Security Considerations

- Ward isolation enforced via `assert_form_ward_access`; superadmin bypasses.
- No mass-assignment: only `final_value`, `confirmed_by`, `status` are set.
