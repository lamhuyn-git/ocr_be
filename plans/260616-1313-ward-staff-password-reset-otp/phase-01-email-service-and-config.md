# Phase 01 — Email service abstraction + config

**Priority:** High · **Status:** ⬜ · Nền tảng cho gửi OTP.

## Mục tiêu
Tạo lớp gửi email provider-agnostic, default SMTP async, cấu hình qua `.env`. Khi scale chỉ đổi env hoặc thêm adapter mới sau interface.

## Requirements
- Async (không block event loop) → `aiosmtplib`.
- Cấu hình: host, port, user, password, from address, TLS.
- Fail-safe: lỗi gửi mail không crash request; log lỗi. (Forgot-password vẫn trả 200 generic.)

## Files
**Create:**
- `app/core/email/__init__.py` — export `get_email_sender()`, `render_otp_email()`.
- `app/core/email/base.py` — `EmailSender` (Protocol/ABC) với `async def send(to, subject, html, text)`.
- `app/core/email/smtp_sender.py` — `SmtpEmailSender(EmailSender)` dùng `aiosmtplib`.
- `app/core/email/console_sender.py` — `ConsoleEmailSender` (log ra stdout) cho dev/test khi SMTP chưa cấu hình.
- `app/core/email/templates/otp_reset.html` — HTML template có branding (logo, màu thương hiệu, mã OTP nổi bật, ghi chú hết hạn).
- `app/core/email/renderer.py` — `render_otp_email(otp, expire_minutes) -> (html, text)` dùng Jinja2, inject brand từ config.

**Modify:**
- `app/config.py` — thêm settings:
  - SMTP: `smtp_host: str = ""`, `smtp_port: int = 587`, `smtp_user: str = ""`, `smtp_password: str = ""`, `smtp_from: str = "no-reply@trulem.local"`, `smtp_use_tls: bool = True`
  - Backend: `email_sender_backend: str = "smtp"`  # smtp | console
  - Brand (cho template): `app_name: str = "Trú Lẹ"`, `brand_logo_url: str = ""`, `brand_color: str = "#2563eb"`, `support_email: str = ""`
- `requirements.txt` — thêm `aiosmtplib==3.0.2`, `jinja2` (nếu chưa có).
- `.env.example` (nếu có) — thêm biến SMTP + brand.

## Implementation steps
1. Định nghĩa `EmailSender` ABC: `send(to: str, subject: str, html: str, text: str | None) -> None`.
2. `SmtpEmailSender`: build `EmailMessage` (multipart: text + html), gửi qua `aiosmtplib.send(...)` với STARTTLS theo `smtp_use_tls`. Bọc try/except → log + raise `EmailSendError` để caller quyết định nuốt lỗi.
3. `ConsoleEmailSender`: log subject + body (dùng khi `email_sender_backend=console` hoặc `smtp_host` rỗng).
4. Factory `get_email_sender()`: chọn backend theo settings; nếu `smtp` mà thiếu `smtp_host` → fallback console + warning.
5. `renderer.py`: load `otp_reset.html` qua Jinja2 `Environment`, render với `{otp, expire_minutes, app_name, brand_logo_url, brand_color, support_email}`; sinh kèm bản `text` fallback đơn giản.
6. Template `otp_reset.html`: header logo, khối mã OTP cỡ lớn dễ đọc, dòng "hết hạn sau X phút", footer hỗ trợ. Inline CSS (email client không hỗ trợ external CSS).

## Success criteria
- `from app.core.email import get_email_sender` import OK, không lỗi compile.
- Với `email_sender_backend=console` gọi `send()` in ra log, không cần SMTP thật.

## Security
- Không log mật khẩu SMTP. Không log nội dung OTP ở mức INFO production (chỉ console backend dev mới log full).
