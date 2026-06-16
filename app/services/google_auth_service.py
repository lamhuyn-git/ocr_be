from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


async def get_or_create_google_user(
    db: AsyncSession, *, google_sub: str, email: str | None,
    email_verified: bool, full_name: str | None,
) -> User:
    # Case 1: Check user đã từng đăng nhập bằng gg vào hệ thống chưa
    user = (await db.execute(select(User).where(User.google_sub == google_sub))).scalar_one_or_none()
    if user:
        return user
    # Case 2. Đã có tài khoản cùng email (đã verify) → link Google vào
    if email and email_verified:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user:
            user.google_sub = google_sub
            return user
    # Case 3. Tạo mới: citizen không mật khẩu (chỉ login qua Google)
    user = User(email=email, full_name=full_name, google_sub=google_sub, hashed_password=None)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user