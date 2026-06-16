from __future__ import annotations
import uuid

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.main import app
from app.database import get_db
from app.config import get_settings
from app.core.rate_limit import limiter
from app.models.user import User
from app.models.organization import Organization, OrganizationMember, OrgRole
from app.core.security import hash_password

settings = get_settings()
# NullPool: mỗi connect() tạo connection mới trên đúng event-loop của test
# (asyncpg gắn với loop → tránh "another operation is in progress").
_engine = create_async_engine(settings.database_url, poolclass=NullPool)


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limiter():
    """Mỗi test bắt đầu với bộ đếm rate-limit sạch (memory storage dùng chung process)."""
    limiter.enabled = True
    limiter.reset()
    yield


@pytest_asyncio.fixture
async def _conn():
    """Một connection + transaction bao quanh mỗi test, rollback ở cuối → DB sạch."""
    async with _engine.connect() as conn:
        trans = await conn.begin()
        try:
            yield conn
        finally:
            if trans.is_active:
                await trans.rollback()


def _make_session(conn) -> AsyncSession:
    # create_savepoint: commit() của app chỉ release savepoint, không đụng transaction ngoài.
    return AsyncSession(bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint")


@pytest_asyncio.fixture
async def db_session(_conn):
    session = _make_session(_conn)
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def client(_conn):
    # App dùng session riêng (cùng connection) và commit như production → test thấy thay đổi.
    async def _override_get_db():
        session = _make_session(_conn)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def staff_user(db_session) -> User:
    """Cán bộ phường (ward_officer) — login bằng email + password."""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"staff_{suffix}@example.com",
        hashed_password=hash_password("OldPass123"),
        full_name="Test Staff",
    )
    db_session.add(user)
    await db_session.flush()
    org = Organization(name="Phường Test", slug=f"phuong-test-{suffix}")
    db_session.add(org)
    await db_session.flush()
    db_session.add(OrganizationMember(org_id=org.id, user_id=user.id, role=OrgRole.ward_officer))
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def citizen_user(db_session) -> User:
    """Công dân — có email nhưng không phải staff → không được reset qua đây."""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        national_id=f"{int(uuid.uuid4().int % 10**12):012d}",
        email=f"citizen_{suffix}@example.com",
        hashed_password=hash_password("OldPass123"),
        full_name="Test Citizen",
    )
    db_session.add(user)
    await db_session.flush()
    return user
