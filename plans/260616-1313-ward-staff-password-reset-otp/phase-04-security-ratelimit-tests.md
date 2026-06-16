# Phase 04 — Hardening, throttle/rate-limit + tests

**Priority:** Medium · **Status:** ⬜ · Depends: Phase 3.

## Mục tiêu
Chống brute-force OTP + spam email, và phủ test cho luồng.

## Constants (đặt trong config)
- `OTP_EXPIRE_MINUTES = 10`
- `OTP_MAX_VERIFY_ATTEMPTS = 5` (vượt → OTP coi như hỏng, phải xin lại)
- `OTP_RESEND_COOLDOWN_SECONDS = 60` (giữa 2 lần forgot cho cùng email)
- Rate-limit IP: `forgot-password` = `5/hour`, `reset-password` = `10/hour` (per IP, chỉnh qua config).
- `ratelimit_storage_uri: str = "memory://"` (đổi sang `redis://...` khi scale nhiều worker).

## Hardening
1. **Throttle gửi (per email, DB)**: forgot-password — nếu OTP active gần nhất của user tạo trong vòng `COOLDOWN` → không tạo/gửi mới (vẫn trả 200 generic).
2. **Brute-force verify**: mỗi lần OTP sai tăng `attempts`; `attempts >= MAX` → từ chối kể cả OTP đúng (buộc xin lại). Test phủ case này.
3. **Generic responses**: xác nhận cả 2 endpoint không tiết lộ email tồn tại/không.
4. **Rate-limit theo IP (`slowapi`)**:
   - Setup `Limiter(key_func=get_remote_address, storage_uri=settings.ratelimit_storage_uri)` trong `app/core/rate_limit.py`.
   - Gắn vào `app.main`: `app.state.limiter = limiter` + `app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)`.
   - Decorator `@limiter.limit("5/hour")` trên `forgot-password`, `@limiter.limit("10/hour")` trên `reset-password` (endpoint cần param `request: Request`).
   - Lưu ý reverse-proxy: nếu deploy sau nginx/load-balancer, cần đọc IP thật từ `X-Forwarded-For` (cấu hình `ProxyHeadersMiddleware` / trusted hosts) — ghi chú deploy.
5. **OTP entropy**: dùng `secrets`, không `random`.
6. **Constant-time compare**: so sánh bằng hash (sha256), verify theo `otp_hash` trong query → tránh timing trên plaintext.

## Tests (`tests/` — theo pattern hiện có)
- `test_forgot_password_staff_creates_otp` — staff email → OTP record tồn tại, mail backend console nhận call.
- `test_forgot_password_citizen_no_otp` — citizen → không tạo OTP, vẫn 200.
- `test_forgot_password_unknown_email_no_leak` — email lạ → 200, không record.
- `test_reset_password_success_revokes_refresh` — OTP đúng → đổi pass + login mới OK + refresh cũ revoked.
- `test_reset_password_wrong_otp_increments_attempts` — sai → 400 + attempts tăng.
- `test_reset_password_expired_otp` — hết hạn → 400.
- `test_reset_password_max_attempts_locks` — quá `MAX` → 400 dù OTP đúng.
- `test_resend_cooldown` — gọi forgot 2 lần liên tiếp → lần 2 không tạo record mới.
- `test_ip_rate_limit_forgot` — vượt ngưỡng/giờ từ 1 IP → 429. (Có thể override limit nhỏ trong test.)

## Success criteria
- Toàn bộ test pass (`pytest`).
- Không lộ user enumeration; brute-force OTP chặn sau `MAX` lần; IP spam chặn bằng 429.

## Unresolved questions (cần brand assets để hoàn thiện template)
1. **Brand assets cho email HTML**: logo URL (ảnh hosted để nhúng vào email), tên hiển thị app, mã màu thương hiệu (hex), email hỗ trợ. → nếu chưa có, tôi dùng placeholder/default và bạn cập nhật sau qua `.env`.
2. **SMTP provider thực tế** sẽ dùng (SES / Mailgun / Gmail …) để điền host/port/credentials khi deploy — giai đoạn dev dùng `console` backend.
