from __future__ import annotations
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import get_user_role
from app.core.email import get_email_sender, render_otp_email, EmailSendError
from app.core.security import hash_token, hash_password
from app.models.user import User, RefreshToken
from app.models.password_reset_otp import PasswordResetOTP

logger = logging.getLogger(__name__)
settings = get_settings()

# Thông báo generic dùng chung — không tiết lộ email có tồn tại hay không.
_GENERIC_FORGOT_MSG = "Nếu email hợp lệ, mã OTP đã được gửi."
_INVALID_OTP_DETAIL = "OTP không hợp lệ hoặc đã hết hạn."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def request_otp(db: AsyncSession, email: str) -> None:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    
    if not user or not user.is_active:
        return
    
    if await get_user_role(user, db) == "citizen":
        return

    cooldown_start = _now() - timedelta(seconds=settings.otp_resend_cooldown_seconds)
    recent = (
        await db.execute(
            select(PasswordResetOTP.id).where(
                PasswordResetOTP.user_id == user.id,
                PasswordResetOTP.is_used == False,  # noqa: E712
                PasswordResetOTP.created_at >= cooldown_start,
            ).limit(1)
        )
    ).scalar_one_or_none()
    if recent:
        return

    await db.execute(
        update(PasswordResetOTP)
        .where(PasswordResetOTP.user_id == user.id, PasswordResetOTP.is_used == False)  # noqa: E712
        .values(is_used=True)
    )

    otp = f"{secrets.randbelow(1_000_000):06d}"
    db.add(PasswordResetOTP(
        user_id=user.id,
        otp_hash=hash_token(otp),
        expires_at=_now() + timedelta(minutes=settings.otp_expire_minutes),
    ))
    await db.flush()

    html, text = render_otp_email(otp, settings.otp_expire_minutes)
    try:
        await get_email_sender().send(
            to=email,
            subject=f"{settings.app_name} — Mã đặt lại mật khẩu",
            html=html,
            text=text,
        )
    except EmailSendError:
        logger.warning("Gửi OTP thất bại cho user %s", user.id)


async def verify_otp(db: AsyncSession, email: str, otp: str) -> None:
    invalid_exc = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_INVALID_OTP_DETAIL)

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user:
        raise invalid_exc

    record = (
        await db.execute(
            select(PasswordResetOTP)
            .where(
                PasswordResetOTP.user_id == user.id,
                PasswordResetOTP.is_used == False,  # noqa: E712
                PasswordResetOTP.expires_at > _now(),
            )
            .order_by(PasswordResetOTP.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if not record or record.attempts >= settings.otp_max_verify_attempts:
        raise invalid_exc

    if record.otp_hash != hash_token(otp):
        # Commit ngay bộ đếm: get_db sẽ rollback khi raise, nên phải persist trước.
        record.attempts += 1
        await db.commit()
        raise invalid_exc
    # Đúng OTP — KHÔNG đánh dấu used; reset_password sẽ tiêu thụ sau.


async def reset_password(db: AsyncSession, email: str, otp: str, new_password: str) -> None:
    """Xác thực OTP và đặt lại mật khẩu. Thành công → revoke toàn bộ refresh token."""
    invalid_exc = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_INVALID_OTP_DETAIL)

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user:
        raise invalid_exc

    # OTP còn hiệu lực gần nhất của user (chưa dùng, chưa hết hạn).
    record = (
        await db.execute(
            select(PasswordResetOTP)
            .where(
                PasswordResetOTP.user_id == user.id,
                PasswordResetOTP.is_used == False,  # noqa: E712
                PasswordResetOTP.expires_at > _now(),
            )
            .order_by(PasswordResetOTP.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if not record or record.attempts >= settings.otp_max_verify_attempts:
        raise invalid_exc

    if record.otp_hash != hash_token(otp):
        # Commit ngay bộ đếm: get_db sẽ rollback khi raise, nên phải persist trước.
        record.attempts += 1
        await db.commit()
        raise invalid_exc

    # Đúng OTP → đổi mật khẩu, đánh dấu đã dùng, buộc đăng nhập lại mọi phiên.
    user.hashed_password = hash_password(new_password)
    record.is_used = True
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.is_revoked == False)  # noqa: E712
        .values(is_revoked=True)
    )
