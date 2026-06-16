# Plan: Cấp lại mật khẩu cho staff (ward_officer + super_admin) qua email OTP

**Created:** 2026-06-16
**Branch:** main
**Status:** Draft — chờ approve

## Mục tiêu
Staff (đăng nhập bằng email: `ward_officer` + `super_admin`) quên mật khẩu → yêu cầu OTP 6 số gửi về email của chính account đó → nhập OTP + mật khẩu mới để đặt lại. Citizen (login bằng CCCD) bị chặn.

## Quyết định đã chốt
- **Email delivery**: lớp trừu tượng `EmailSender`, default impl = **SMTP async (`aiosmtplib`)** trỏ provider transactional (SES/Mailgun/Resend SMTP). Provider-agnostic, scale bằng đổi env, không lock SDK.
- **Flow**: OTP 6 số, hạn 10 phút, dùng 1 lần, hashed trong DB.
- **Scope**: chỉ staff (`ward_officer` + `super_admin`), login bằng **email do hệ thống cấp + password**. Staff KHÔNG dùng Google login → staff luôn có `hashed_password`. Citizen (Google/CCCD) bị chặn bằng kiểm tra role.
- **Email template**: HTML có branding (logo + màu thương hiệu), không phải text trơn. Cần brand assets (xem Unresolved).
- **Rate-limit**: 2 lớp — (a) throttle theo email (cooldown 60s, DB), (b) **rate-limit theo IP** bằng `slowapi` trên cả 2 endpoint.
- **Chống lộ thông tin**: `/forgot-password` luôn trả 200 generic, không tiết lộ email tồn tại hay không.

## Kiến trúc tổng thể
```
POST /auth/forgot-password {email}
  → tìm user theo email; nếu là staff hợp lệ → tạo OTP, hash, lưu, gửi mail
  → LUÔN trả 200 {message generic}

POST /auth/reset-password {email, otp, new_password}
  → verify OTP (hash match + chưa hết hạn + chưa dùng + attempts < max)
  → cập nhật hashed_password, mark OTP used, revoke toàn bộ refresh_tokens của user
  → trả 200
```

## Phases
| # | File | Mô tả | Status |
|---|------|-------|--------|
| 1 | [phase-01-email-service-and-config.md](phase-01-email-service-and-config.md) | `EmailSender` abstraction + SMTP impl + config env | ✅ |
| 2 | [phase-02-otp-model-and-migration.md](phase-02-otp-model-and-migration.md) | Model `PasswordResetOTP` + migration 017 | ✅ |
| 3 | [phase-03-forgot-reset-endpoints.md](phase-03-forgot-reset-endpoints.md) | Schemas + service + routes `auth_password.py` | ✅ |
| 4 | [phase-04-security-ratelimit-tests.md](phase-04-security-ratelimit-tests.md) | Rate-limit, throttle OTP, hardening + tests | ✅ |

**Đã implement xong — 9/9 test pass, migration 017 round-trip OK.**

## Dependencies (mới — thêm vào requirements.txt)
- `aiosmtplib` — gửi SMTP async.
- `jinja2` — render HTML email template (nếu chưa có sẵn qua starlette).
- `slowapi` — rate-limit theo IP.
- Tái dùng: `hash_token` (sha256) cho OTP hash, `hash_password`, pattern `RefreshToken` revoke, `frontend_url`, `get_user_role`.

## Lưu ý scale rate-limit
`slowapi` mặc định lưu counter **in-memory** (đủ cho 1 worker). Khi scale nhiều worker/instance, đổi `storage_uri` sang Redis (config-switchable) — KHÔNG đổi code logic. Plan để storage URI trong config, default in-memory.

## Out of scope
- Đổi mật khẩu khi đã đăng nhập (đã có `/auth/change-password`).
- Reset cho citizen (login bằng CCCD).
- Email verification / welcome email (chỉ làm OTP reset).
