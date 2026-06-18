from __future__ import annotations
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str
    sync_database_url: str
    secret_key: str
    upload_dir: str = "uploads"
    max_file_size_mb: int = 20
    allowed_extensions: str = "jpg,jpeg,png,bmp,tiff,webp,pdf"
    paddleocr_lang: str = "en"
    debug: bool = True

    # AWS credentials + region — dùng chung cho mọi service AWS (S3, SES, SQS…).
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = ""

    # S3 / object storage (presigned upload). Để trống endpoint = dùng AWS thật;
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_public_url_base: str = ""  
    s3_use_path_style: bool = False 
    s3_presign_expire_seconds: int = 3600

    # OCR pipeline (ocr-pipeline package) — chọn model fine-tune trong models/{version}/inference
    ocr_model_version: str = "paddle_v12"

    # form_type_id của đơn "đăng ký tạm trú" → submit sẽ tạo thêm bảng con TamtruForm
    tamtru_form_type_id: str = "96a50bdd-3b78-4f9e-9a12-4a1d86d34732"

    # Hồ sơ quá số ngày này mà chưa xử lý → đánh dấu overdue
    overdue_days: int = 7
    # Hồ sơ kẹt ở 'processing' quá số phút này (OCR chết giữa chừng/restart) → tự kích hoạt lại trích xuất
    stale_processing_minutes: int = 15

    # Auth
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    frontend_url: str = ""

    # Email (SMTP) — gửi OTP đặt lại mật khẩu cho cán bộ
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@vextract.com"
    smtp_use_tls: bool = True
    email_sender_backend: str = "smtp"

    # Branding cho email template
    app_name: str = "VExtract"
    brand_logo_url: str = ""
    brand_color: str = "#133524"
    support_email: str = ""

    # Password reset OTP
    otp_expire_minutes: int = 1
    otp_max_verify_attempts: int = 5
    otp_resend_cooldown_seconds: int = 1

    ratelimit_enabled: bool = True  # đặt false ở dev để tắt limiter (không trả 429)
    ratelimit_storage_uri: str = "memory://"
    ratelimit_forgot_password: str = "5/hour"
    ratelimit_reset_password: str = "10/hour"

    @property
    def allowed_ext_set(self) -> set[str]:
        return {ext.strip().lower() for ext in self.allowed_extensions.split(",")}

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
