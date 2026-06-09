"""Smoke-test harness: rollback-per-test against the real Postgres, OCR stubbed.

Each test runs inside an outer transaction that is rolled back on teardown, so no
test data persists. The OCR background task is replaced with a no-op so `submit_form`
doesn't spawn the real PaddleOCR pipeline or its own DB session.
"""
from __future__ import annotations

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.config import get_settings
from app.database import get_db
from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.models.organization import Organization, OrganizationMember, OrgRole
import app.api.v1.routes.form as form_routes


@pytest_asyncio.fixture
async def db_session():
    """Connection-bound session; outer transaction rolled back after each test.

    Uses a per-test NullPool engine so no connection is reused across pytest-asyncio's
    per-test event loops (avoids 'Event loop is closed' on teardown)."""
    test_engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    conn = await test_engine.connect()
    trans = await conn.begin()
    Session = async_sessionmaker(
        bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    session = Session()
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()
        await test_engine.dispose()


@pytest_asyncio.fixture
async def client(db_session, monkeypatch):
    async def _override_get_db():
        yield db_session

    # Stub the OCR background task so submit_form doesn't run the real pipeline.
    async def _noop_bg(*args, **kwargs):
        return None

    monkeypatch.setattr(form_routes, "_process_form_bg", _noop_bg)
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Factories ───────────────────────────────────────────────────────────────

def _rand_cccd() -> str:
    return uuid.uuid4().int.__str__()[:12].zfill(12)


@pytest_asyncio.fixture
async def make_user(db_session):
    async def _make(
        email: str | None = None,
        is_superuser: bool = False,
        national_id: str | None = None,
        password: str | None = None,
    ) -> User:
        # Default uses a static hash (fast — most tests auth via minted JWT, not login).
        # Pass `password` when the test needs real login verification.
        user = User(
            national_id=national_id or _rand_cccd(),
            email=email or f"{uuid.uuid4().hex[:8]}@test.local",
            hashed_password=hash_password(password) if password else "x" * 60,
            full_name="Test",
            is_superuser=is_superuser,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        return user
    return _make


@pytest_asyncio.fixture
async def make_ward(db_session):
    async def _make(name: str = "Ward") -> Organization:
        org = Organization(name=name, slug=f"{name.lower()}-{uuid.uuid4().hex[:6]}")
        db_session.add(org)
        await db_session.flush()
        await db_session.refresh(org)
        return org
    return _make


@pytest_asyncio.fixture
async def make_officer(db_session):
    async def _make(user: User, ward: Organization, role: OrgRole = OrgRole.ward_officer):
        m = OrganizationMember(org_id=ward.id, user_id=user.id, role=role)
        db_session.add(m)
        await db_session.flush()
        return m
    return _make


def auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
