# Phase 02 — Model PasswordResetOTP + migration 017

**Priority:** High · **Status:** ⬜ · Depends: none (song song được với Phase 1).

## Mục tiêu
Lưu OTP an toàn: hash (không lưu plaintext), có hạn, dùng 1 lần, đếm số lần verify sai.

## Files
**Create:**
- `app/models/password_reset_otp.py` — model `PasswordResetOTP`.
- `alembic/versions/017_add_password_reset_otps.py` — migration (revision `017`, down_revision `016`).

**Modify:**
- `app/models/__init__.py` — export model mới (để Alembic autogenerate / metadata thấy).

## Schema bảng `password_reset_otps`
| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| id | UUID PK | default uuid4 |
| user_id | UUID FK users.id ON DELETE CASCADE | index |
| otp_hash | String(128) | sha256 hex của OTP (tái dùng `hash_token`) |
| expires_at | DateTime(tz) | now + 10 phút |
| attempts | Integer | default 0, đếm verify sai |
| is_used | Boolean | default False |
| created_at | DateTime(tz) | server_default now |

- Index `ix_password_reset_otps_user_id`.
- Không unique trên `otp_hash` (OTP 6 số có thể trùng giữa user khác nhau — verify luôn theo `user_id` + `otp_hash`).

## Implementation steps
1. Viết model theo style `RefreshToken` trong `app/models/user.py` (Column + relationship optional).
2. Migration `017`: `op.create_table(...)` + `op.create_index(...)`; `downgrade` drop index + table.
3. Đảm bảo model được import trong `app/models/__init__.py`.

## Success criteria
- `alembic upgrade head` chạy được, tạo bảng.
- `alembic downgrade -1` rollback sạch.

## Security
- Chỉ lưu hash OTP, không plaintext.
- TTL ngắn (10 phút) + single-use chống replay.
