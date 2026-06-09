"""Internal-auth smoke tests: admin-gated registration + CCCD login."""
from __future__ import annotations

import pytest

from app.models.organization import OrgRole
from tests.conftest import auth


# ── /auth/register is admin-only ───────────────────────────────────────────────

async def test_register_requires_auth(client):
    r = await client.post("/api/v1/auth/register",
                          json={"national_id": "111122223333", "password": "secret12"})
    assert r.status_code in (401, 403)


async def test_citizen_cannot_register(client, make_user):
    citizen = await make_user()  # no membership, not superuser
    r = await client.post("/api/v1/auth/register", headers=auth(citizen),
                          json={"national_id": "111122223333", "password": "secret12"})
    assert r.status_code == 403


async def test_superadmin_can_register(client, make_user):
    admin = await make_user(is_superuser=True)
    r = await client.post("/api/v1/auth/register", headers=auth(admin),
                          json={"national_id": "111122223333", "password": "secret12",
                                "full_name": "Dân A"})
    assert r.status_code == 201
    body = r.json()
    assert body["national_id"] == "111122223333"
    assert body["is_superuser"] is False  # new accounts are plain citizens


async def test_ward_officer_cannot_register(client, db_session, make_user, make_ward, make_officer):
    user = await make_user()
    ward = await make_ward()
    await make_officer(user, ward, role=OrgRole.ward_officer)
    r = await client.post("/api/v1/auth/register", headers=auth(user),
                          json={"national_id": "444455556666", "password": "secret12"})
    assert r.status_code == 403  # only super_admin may register accounts


# ── validation ─────────────────────────────────────────────────────────────────

async def test_register_duplicate_national_id(client, make_user):
    admin = await make_user(is_superuser=True)
    await make_user(national_id="777788889999")
    r = await client.post("/api/v1/auth/register", headers=auth(admin),
                          json={"national_id": "777788889999", "password": "secret12"})
    assert r.status_code == 409


async def test_register_bad_cccd_format(client, make_user):
    admin = await make_user(is_superuser=True)
    r = await client.post("/api/v1/auth/register", headers=auth(admin),
                          json={"national_id": "abc", "password": "secret12"})
    assert r.status_code == 422


# ── /auth/login by CCCD ─────────────────────────────────────────────────────────

async def test_login_by_cccd(client, make_user):
    await make_user(national_id="121212121212", password="secret12")
    ok = await client.post("/api/v1/auth/login/citizen",
                           json={"national_id": "121212121212", "password": "secret12"})
    assert ok.status_code == 200
    assert "access_token" in ok.json()

    bad = await client.post("/api/v1/auth/login/citizen",
                            json={"national_id": "121212121212", "password": "wrongpass"})
    assert bad.status_code == 401


async def test_staff_login_by_email(client, db_session, make_user, make_ward, make_officer):
    # ward_officer with email account → can use staff login
    officer = await make_user(email="officer@ward.gov", password="secret12")
    ward = await make_ward()
    await make_officer(officer, ward)
    ok = await client.post("/api/v1/auth/login/staff",
                           json={"email": "officer@ward.gov", "password": "secret12"})
    assert ok.status_code == 200 and "access_token" in ok.json()

    # wrong password → 401
    bad = await client.post("/api/v1/auth/login/staff",
                            json={"email": "officer@ward.gov", "password": "nope1234"})
    assert bad.status_code == 401


async def test_staff_login_rejects_citizen(client, make_user):
    # citizen has an email but no membership → blocked from staff door
    await make_user(email="citizen@x.com", password="secret12")
    r = await client.post("/api/v1/auth/login/staff",
                          json={"email": "citizen@x.com", "password": "secret12"})
    assert r.status_code == 403


async def test_me_returns_profile_and_role(client, db_session, make_user, make_ward, make_officer):
    officer = await make_user(national_id="151515151515")
    ward = await make_ward()
    await make_officer(officer, ward)
    r = await client.get("/api/v1/auth/me", headers=auth(officer))
    assert r.status_code == 200
    body = r.json()
    assert body["national_id"] == "151515151515"
    assert body["role"] == "ward_officer"
    assert "full_name" in body  # FE maps full_name → name

    citizen = await make_user()
    rc = await client.get("/api/v1/auth/me", headers=auth(citizen))
    assert rc.json()["role"] == "citizen"
