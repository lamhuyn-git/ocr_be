"""Smoke tests for the 3-role ward form system: data isolation, ward scoping,
review-flow transitions, and status history."""
from __future__ import annotations

import uuid
import pytest

from app.models.form import Form as FormModel, FormStatus, FormTemplate, FormStatusHistory
from app.models.organization import OrgRole
from tests.conftest import auth


async def _make_form(db, *, created_by, org_id, status=FormStatus.submitted) -> FormModel:
    form = FormModel(
        org_id=org_id,
        created_by=created_by,
        form_id="ct01",
        original_filename="f.png",
        file_path="/tmp/f.png",
        file_size=10,
        status=status,
    )
    db.add(form)
    await db.flush()
    await db.refresh(form)
    return form


# ── Data isolation: citizen ───────────────────────────────────────────────────

async def test_citizen_sees_only_own_form(client, db_session, make_user, make_ward):
    citizen_a = await make_user()
    citizen_b = await make_user()
    ward = await make_ward()
    form = await _make_form(db_session, created_by=citizen_a.id, org_id=ward.id)

    # Owner can read; other citizen cannot.
    assert (await client.get(f"/api/v1/form/{form.id}", headers=auth(citizen_a))).status_code == 200
    assert (await client.get(f"/api/v1/form/{form.id}", headers=auth(citizen_b))).status_code == 403

    # citizen_b's list excludes it.
    r = await client.get("/api/v1/form", headers=auth(citizen_b))
    assert r.status_code == 200
    assert all(item["id"] != str(form.id) for item in r.json()["items"])


# ── Ward scoping: officers ─────────────────────────────────────────────────────

async def test_officer_ward_scoping(client, db_session, make_user, make_ward, make_officer):
    citizen = await make_user()
    ward_a, ward_b = await make_ward("Alpha"), await make_ward("Beta")
    officer_a, officer_b = await make_user(), await make_user()
    await make_officer(officer_a, ward_a)
    await make_officer(officer_b, ward_b)
    form_a = await _make_form(db_session, created_by=citizen.id, org_id=ward_a.id)

    # Officer of ward A sees it; officer of ward B is forbidden.
    assert (await client.get(f"/api/v1/form/{form_a.id}", headers=auth(officer_a))).status_code == 200
    assert (await client.get(f"/api/v1/form/{form_a.id}", headers=auth(officer_b))).status_code == 403

    la = await client.get("/api/v1/form", headers=auth(officer_a))
    assert any(i["id"] == str(form_a.id) for i in la.json()["items"])
    lb = await client.get("/api/v1/form", headers=auth(officer_b))
    assert all(i["id"] != str(form_a.id) for i in lb.json()["items"])


async def test_super_admin_sees_all_and_history(client, db_session, make_user, make_ward):
    citizen = await make_user()
    superu = await make_user(is_superuser=True)
    ward = await make_ward()
    form = await _make_form(db_session, created_by=citizen.id, org_id=ward.id)

    assert (await client.get(f"/api/v1/form/{form.id}", headers=auth(superu))).status_code == 200
    h = await client.get(f"/api/v1/form/{form.id}/history", headers=auth(superu))
    assert h.status_code == 200


# ── Review flow + transition preconditions ─────────────────────────────────────

async def test_review_flow_and_precondition(client, db_session, make_user, make_ward, make_officer):
    citizen = await make_user()
    officer = await make_user()
    other_officer = await make_user()
    ward_a, ward_b = await make_ward("Alpha"), await make_ward("Beta")
    await make_officer(officer, ward_a)
    await make_officer(other_officer, ward_b)
    form = await _make_form(db_session, created_by=citizen.id, org_id=ward_a.id)

    # Precondition: cannot review a form still in `submitted`.
    assert (await client.post(f"/api/v1/form/{form.id}/review", headers=auth(officer))).status_code == 409

    # Simulate OCR done.
    form.status = FormStatus.extracted
    await db_session.flush()

    # Cross-ward officer is forbidden from reviewing.
    assert (await client.post(f"/api/v1/form/{form.id}/review", headers=auth(other_officer))).status_code == 403

    # Happy path: review → decision(approved) → result(returned).
    r1 = await client.post(f"/api/v1/form/{form.id}/review", headers=auth(officer))
    assert r1.status_code == 200 and r1.json()["status"] == "under_review"

    r2 = await client.post(f"/api/v1/form/{form.id}/decision",
                           headers=auth(officer), json={"decision": "approved", "note": "ok"})
    assert r2.status_code == 200 and r2.json()["status"] == "approved"
    assert r2.json()["reviewed_by"] == str(officer.id)

    r3 = await client.post(f"/api/v1/form/{form.id}/result",
                           headers=auth(officer), json={"result_message": "Đã cấp"})
    assert r3.status_code == 200 and r3.json()["status"] == "returned"

    # History has the three transitions in order.
    h = await client.get(f"/api/v1/form/{form.id}/history", headers=auth(officer))
    tos = [row["to_status"] for row in h.json()]
    assert tos == ["under_review", "approved", "returned"]


# ── submit_form: ward (org_id) required + validated ─────────────────────────────

async def test_submit_requires_valid_ward(client, db_session, make_user, make_ward):
    citizen = await make_user()
    ward = await make_ward()
    db_session.add(FormTemplate(form_id="ct01", name="CT01", version="1.0",
                                config_path="/tmp/ct01.yaml", is_active=True))
    await db_session.flush()
    img = ("f.png", b"\x89PNG\r\n\x1a\n", "image/png")

    # Missing org_id → 422 (validation).
    r_missing = await client.post("/api/v1/form", headers=auth(citizen),
                                  data={"form_id": "ct01"}, files={"image": img})
    assert r_missing.status_code == 422

    # Non-existent ward → 404.
    r_bad = await client.post("/api/v1/form", headers=auth(citizen),
                              data={"form_id": "ct01", "org_id": str(uuid.uuid4())},
                              files={"image": img})
    assert r_bad.status_code == 404

    # Valid ward → 202, status submitted, one initial history row.
    r_ok = await client.post("/api/v1/form", headers=auth(citizen),
                             data={"form_id": "ct01", "org_id": str(ward.id)},
                             files={"image": img})
    assert r_ok.status_code == 202
    assert r_ok.json()["status"] == "submitted"
    form_id = r_ok.json()["form_id_db"]
    h = await client.get(f"/api/v1/form/{form_id}/history", headers=auth(citizen))
    assert [row["to_status"] for row in h.json()] == ["submitted"]
