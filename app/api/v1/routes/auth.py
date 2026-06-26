from datetime import datetime, timezone, date
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from fastapi.security import HTTPBearer
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt
from uuid import UUID

from app.database import get_db
from app.config import get_settings
from app.core.oauth import oauth
from app.core.rate_limit import limiter
from app.core.security import (hash_password, verify_password, hash_token,create_access_token, create_refresh_token, decode_token,)
from app.core.deps import get_current_user, get_current_superuser, get_user_role, get_user_primary_ward
from app.models.user import User, RefreshToken
from app.models.form import FormStatus
from app.schemas.auth import ( RegisterRequest, LoginRequest, StaffLoginRequest,TokenResponse, RefreshRequest,)
from app.schemas.form import FormResponse
from app.schemas.user import UserResponse, WardAssignment
from app.schemas.password_reset import (ForgotPasswordRequest, VerifyOtpRequest, ResetPasswordRequest, MessageResponse,)
from app.services.google_auth_service import get_or_create_google_user
from app.services.password_reset_service import request_otp, verify_otp, reset_password

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer = HTTPBearer()
settings = get_settings()


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
    # hashed_password có thể là None với tài khoản chỉ đăng nhập qua Google → chặn trước khi verify.
    if not user or not user.hashed_password or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return await _issue_tokens(user, db)


@router.post("/login/staff", response_model=TokenResponse, summary="Staff login (by email account)")
async def login_staff(body: StaffLoginRequest, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    # hashed_password có thể là None với tài khoản chỉ đăng nhập qua Google → chặn trước khi verify.
    if not user or not user.hashed_password or not verify_password(body.password, user.hashed_password):
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
async def me(current_user: User = Depends(get_current_user),db: AsyncSession = Depends(get_db),):
    resp = UserResponse.model_validate(current_user)
    resp.role = await get_user_role(current_user, db)
    if resp.role == "ward_officer":
        ward = await get_user_primary_ward(current_user, db)
        if ward:
            resp.ward = WardAssignment(**ward)
    return resp


@router.post("/forgot-password", response_model=MessageResponse, summary="Gửi OTP đặt lại mật khẩu (tài khoản cán bộ)")
@limiter.limit(settings.ratelimit_forgot_password)
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    await request_otp(db, body.email)
    return MessageResponse(message="Nếu email hợp lệ, mã OTP đã được gửi đến email.")


@router.post("/verify-otp", response_model=MessageResponse, summary="Xác minh OTP (chưa đổi mật khẩu)")
@limiter.limit(settings.ratelimit_reset_password)
async def verify_otp_endpoint(
    request: Request,
    body: VerifyOtpRequest,
    db: AsyncSession = Depends(get_db),
):
    await verify_otp(db, body.email, body.otp)
    return MessageResponse(message="OTP hợp lệ.")


@router.post("/reset-password", response_model=MessageResponse, summary="Đặt lại mật khẩu bằng OTP")
@limiter.limit(settings.ratelimit_reset_password)
async def reset_password_endpoint(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    await reset_password(db, body.email, body.otp, body.new_password)
    return MessageResponse(message="Đặt lại mật khẩu thành công.")


def _login_error(reason: str, status_code: int, detail: str):
    if settings.frontend_url:
        qs = urlencode({"error": reason})
        return RedirectResponse(url=f"{settings.frontend_url}/login?{qs}")
    raise HTTPException(status_code, detail)


@router.get("/google/login", summary="Bắt đầu đăng nhập Google")
async def google_login(request: Request):
    callback_uri = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(request, callback_uri)


@router.get("/google/callback", name="google_callback", summary="Xử lý phản hồi từ Google sau đăng nhập")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        # Kiểm tra danh tính trên gg bằng cách kiểm state + đổi code lấy token + verify & bóc userinfo
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return _login_error("google_auth_failed", status.HTTP_401_UNAUTHORIZED, "Google authentication failed")
    info = token.get("userinfo")
    if not info:
        return _login_error("no_user_info", status.HTTP_401_UNAUTHORIZED, "No user info from Google")

    user = await get_or_create_google_user(
        db,
        google_sub=info["sub"],
        email=info.get("email"),
        email_verified=bool(info.get("email_verified")),
        full_name=info.get("name"),
    )
    if not user.is_active:
        return _login_error("account_disabled", status.HTTP_403_FORBIDDEN, "This account is prevented.")

    # Cổng Google chỉ dành cho công dân; cán bộ/admin dùng cổng đăng nhập email + mật khẩu.
    if await get_user_role(user, db) != "citizen":
        return _login_error("not_citizen", status.HTTP_403_FORBIDDEN, "Tài khoản này không được đăng nhập bằng Google")

    tokens = await _issue_tokens(user, db)
    if settings.frontend_url:
        qs = urlencode({"access_token": tokens.access_token, "refresh_token": tokens.refresh_token})
        return RedirectResponse(url=f"{settings.frontend_url}/auth/callback?{qs}")
    return JSONResponse(tokens.model_dump())

# @router.get("/list-form",response_model=list[FormResponse],summary="List submitted form by user id")
# async def list_form_by_user_id(
#     type_id: UUID | None = None,
#     organization_id: UUID | None = None,
#     status_filter: FormStatus | None = Query(default=None, alias="status"),
#     date_from: date | None = Query(default=None, description="Lọc các form được nộp từ ngày này"),
#     date_to: date | None = Query(default=None, description="Lọc các form được nộp đến hết ngày này"),
#     page: int = 1,
#     page_size: int = 10,
#     current_user: User = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):