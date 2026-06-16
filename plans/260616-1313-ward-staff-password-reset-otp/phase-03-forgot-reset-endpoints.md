# Phase 03 — Schemas + service + endpoints

**Priority:** High · **Status:** ⬜ · Depends: Phase 1, 2.

## Mục tiêu
2 endpoint: `POST /auth/forgot-password`, `POST /auth/reset-password`. Tách file riêng `auth_password.py` (giữ `auth.py` < 200 dòng).

## Files
**Create:**
- `app/schemas/password_reset.py` — `ForgotPasswordRequest`, `ResetPasswordRequest`.
- `app/services/password_reset_service.py` — logic tạo/verify OTP, gửi mail, đặt lại mật khẩu.
- `app/api/v1/routes/auth_password.py` — router `prefix="/auth"`.

**Modify:**
- `app/api/v1/routes/__init__.py` — include router mới (giống cách include `auth_google`).

## Schemas
```python
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8)
```

## Service logic (`password_reset_service.py`)
**`request_otp(db, email)`**
1. Tìm user theo email.
2. Nếu không có user / `get_user_role(user, db) == "citizen"` / không `is_active` → return im lặng (KHÔNG gửi mail, KHÔNG báo lỗi). Staff luôn có `hashed_password` (login email+password do hệ thống cấp, không Google) → không cần xử lý case account chỉ-Google.
3. Throttle: nếu có OTP chưa hết hạn tạo < 60s trước → bỏ qua tạo mới (chống spam). (Chi tiết Phase 4.)
4. Sinh OTP 6 số bằng `secrets.randbelow(1_000_000)` → zero-pad. Hash bằng `hash_token`. Lưu record. Invalidate (mark used) các OTP cũ chưa dùng của user.
5. Render email qua `render_otp_email(...)` + gửi qua `get_email_sender().send(...)`; nuốt `EmailSendError` (log) để không lộ trạng thái.

**`reset_password(db, email, otp, new_password)`**
1. Tìm user theo email; nếu không có → raise 400 generic "OTP không hợp lệ hoặc đã hết hạn".
2. Lấy OTP record mới nhất chưa dùng của user: match `otp_hash`, `is_used == False`, `expires_at > now`, `attempts < MAX_ATTEMPTS`.
3. Sai → tăng `attempts` của record ứng viên (nếu tìm thấy theo user) → raise 400 generic.
4. Đúng → `user.hashed_password = hash_password(new_password)`; `otp.is_used = True`; revoke toàn bộ `RefreshToken` của user (`is_revoked = True`) để buộc đăng nhập lại.

## Endpoints (`auth_password.py`)
- `POST /auth/forgot-password` → gọi `request_otp`, luôn `return {"message": "Nếu email hợp lệ, mã OTP đã được gửi."}` (200).
- `POST /auth/reset-password` → gọi `reset_password`, trả `{"message": "Đặt lại mật khẩu thành công."}` (200).

## Success criteria
- Forgot với email staff hợp lệ → có record OTP + mail gửi (console log ở dev).
- Forgot với email citizen / không tồn tại → vẫn 200, không tạo record, không gửi mail.
- Reset đúng OTP → đăng nhập `/auth/login/staff` bằng mật khẩu mới OK; refresh token cũ bị revoke.

## Security
- Response generic cho cả forgot & reset (chống user enumeration).
- OTP single-use; revoke refresh tokens sau reset.
