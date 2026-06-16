from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from sqlalchemy import select, func

from app.models.user import RefreshToken
from app.models.password_reset_otp import PasswordResetOTP
from app.core.security import hash_token, verify_password

FORGOT = "/api/v1/auth/forgot-password"
RESET = "/api/v1/auth/reset-password"


@pytest_asyncio.fixture
def captured_emails(monkeypatch):
    """Bắt email gửi đi thay vì gửi thật → đọc được OTP để test luồng reset."""
    box: list[dict] = []

    class _FakeSender:
        async def send(self, to, subject, html, text=None):
            box.append({"to": to, "subject": subject, "html": html, "text": text})

    monkeypatch.setattr(
        "app.services.password_reset_service.get_email_sender", lambda: _FakeSender()
    )
    return box


def _extract_otp(email: dict) -> str:
    m = re.search(r"\b(\d{6})\b", email["text"])
    assert m, "Không tìm thấy OTP trong email"
    return m.group(1)


async def _count_otps(db, user_id) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(PasswordResetOTP).where(
                PasswordResetOTP.user_id == user_id
            )
        )
    ).scalar_one()


# ---------- forgot-password ----------

async def test_forgot_password_staff_creates_otp_and_sends(client, db_session, staff_user, captured_emails):
    r = await client.post(FORGOT, json={"email": staff_user.email})
    assert r.status_code == 200
    assert await _count_otps(db_session, staff_user.id) == 1
    assert len(captured_emails) == 1
    assert captured_emails[0]["to"] == staff_user.email


async def test_forgot_password_citizen_no_otp(client, db_session, citizen_user, captured_emails):
    r = await client.post(FORGOT, json={"email": citizen_user.email})
    assert r.status_code == 200  # vẫn generic, không lộ
    assert await _count_otps(db_session, citizen_user.id) == 0
    assert captured_emails == []


async def test_forgot_password_unknown_email_no_leak(client, captured_emails):
    r = await client.post(FORGOT, json={"email": "nobody@example.com"})
    assert r.status_code == 200
    assert captured_emails == []


async def test_resend_cooldown(client, db_session, staff_user, captured_emails):
    await client.post(FORGOT, json={"email": staff_user.email})
    await client.post(FORGOT, json={"email": staff_user.email})  # trong cooldown → bỏ qua
    assert await _count_otps(db_session, staff_user.id) == 1
    assert len(captured_emails) == 1


# ---------- reset-password ----------

async def test_reset_password_success_revokes_refresh(client, db_session, staff_user, captured_emails):
    # tạo một refresh token đang sống để kiểm tra bị revoke
    db_session.add(RefreshToken(
        user_id=staff_user.id, token_hash="live-token-hash",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    ))
    await db_session.flush()

    await client.post(FORGOT, json={"email": staff_user.email})
    otp = _extract_otp(captured_emails[0])

    r = await client.post(RESET, json={
        "email": staff_user.email, "otp": otp, "new_password": "BrandNew123",
    })
    assert r.status_code == 200

    await db_session.refresh(staff_user)
    assert verify_password("BrandNew123", staff_user.hashed_password)

    revoked = (
        await db_session.execute(
            select(RefreshToken.is_revoked).where(RefreshToken.user_id == staff_user.id)
        )
    ).scalars().all()
    assert all(revoked)


async def _make_otp(db, user_id, code="123456", *, minutes=10, attempts=0, used=False):
    rec = PasswordResetOTP(
        user_id=user_id,
        otp_hash=hash_token(code),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=minutes),
        attempts=attempts,
        is_used=used,
    )
    db.add(rec)
    await db.flush()
    return rec


async def test_reset_password_wrong_otp_increments_attempts(client, db_session, staff_user):
    rec = await _make_otp(db_session, staff_user.id, "123456")
    r = await client.post(RESET, json={
        "email": staff_user.email, "otp": "000000", "new_password": "BrandNew123",
    })
    assert r.status_code == 400
    await db_session.refresh(rec)
    assert rec.attempts == 1


async def test_reset_password_expired_otp(client, db_session, staff_user):
    await _make_otp(db_session, staff_user.id, "123456", minutes=-1)
    r = await client.post(RESET, json={
        "email": staff_user.email, "otp": "123456", "new_password": "BrandNew123",
    })
    assert r.status_code == 400


async def test_reset_password_max_attempts_locks(client, db_session, staff_user):
    await _make_otp(db_session, staff_user.id, "123456", attempts=5)
    r = await client.post(RESET, json={
        "email": staff_user.email, "otp": "123456", "new_password": "BrandNew123",
    })
    assert r.status_code == 400  # đúng OTP nhưng đã quá số lần thử


# ---------- rate limit (IP) ----------

async def test_ip_rate_limit_forgot(client, captured_emails):
    # limit mặc định 5/hour → request thứ 6 bị chặn 429
    last = None
    for _ in range(6):
        last = await client.post(FORGOT, json={"email": "nobody@example.com"})
    assert last.status_code == 429
