from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt

from app.database import get_db
from app.models.user import User, RefreshToken
from app.schemas.auth import (
    RegisterRequest, LoginRequest, StaffLoginRequest,
    TokenResponse, RefreshRequest, ChangePasswordRequest,
)
from app.schemas.user import UserResponse
from app.core.security import (
    hash_password, verify_password, hash_token,
    create_access_token, create_refresh_token, decode_token,
)
from app.core.deps import get_current_user, get_current_superuser, get_user_role

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer = HTTPBearer()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    dup_id = (await db.execute(select(User).where(User.national_id == body.national_id))).scalar_one_or_none()
    if dup_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="National ID already registered")
    if body.email:
        dup_email = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
        if dup_email:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        national_id=body.national_id,
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def _issue_tokens(user: User, db: AsyncSession) -> TokenResponse:
    """Create access + refresh tokens for an authenticated user and persist the refresh token."""
    access_token = create_access_token(str(user.id))
    raw_refresh, expires_at = create_refresh_token(str(user.id))
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=expires_at,
    ))
    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post("/login/citizen", response_model=TokenResponse, summary="Citizen login (by CCCD)")
async def login_citizen(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.national_id == body.national_id))).scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return await _issue_tokens(user, db)


@router.post("/login/staff", response_model=TokenResponse, summary="Staff login (by email account)")
async def login_staff(body: StaffLoginRequest, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    # Staff portal: only super_admin or ward staff may use this door.
    if await get_user_role(user, db) == "citizen":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a staff account")
    return await _issue_tokens(user, db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    credentials_exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise credentials_exc
        user_id: str = payload["sub"]
    except jwt.PyJWTError:
        raise credentials_exc

    token_hash = hash_token(body.refresh_token)
    stored = (
        await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked == False,
            )
        )
    ).scalar_one_or_none()

    if not stored or stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise credentials_exc

    stored.is_revoked = True
    new_access = create_access_token(user_id)
    raw_refresh, expires_at = create_refresh_token(user_id)
    db.add(RefreshToken(user_id=stored.user_id, token_hash=hash_token(raw_refresh), expires_at=expires_at))

    return TokenResponse(access_token=new_access, refresh_token=raw_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    token_hash = hash_token(body.refresh_token)
    stored = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if stored and stored.user_id == current_user.id:
        stored.is_revoked = True


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Current user's profile + derived role — FE's single source after login."""
    resp = UserResponse.model_validate(current_user)
    resp.role = await get_user_role(current_user, db)
    return resp


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(body.new_password)
