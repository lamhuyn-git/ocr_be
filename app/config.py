from __future__ import annotations
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/ocr_db"
    sync_database_url: str = "postgresql://postgres:password@localhost:5432/ocr_db"
    upload_dir: str = "uploads"
    max_file_size_mb: int = 20
    allowed_extensions: str = "jpg,jpeg,png,bmp,tiff,webp,pdf"
    paddleocr_lang: str = "en"
    debug: bool = True

    # Auth
    secret_key: str = "change-me-in-production-use-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Seed (scripts/seed_admin.py) — initial accounts for an internal, admin-provisioned system
    seed_admin_national_id: str = "000000000001"
    seed_admin_password: str = "change-me-admin"
    seed_admin_email: str | None = "superadmin@local"
    seed_admin_full_name: str = "Super Admin"
    seed_ward_officer_national_id: str = "000000000002"
    seed_ward_officer_password: str = "change-me-ward"
    seed_ward_officer_full_name: str = "Ward Officer"
    seed_ward_name: str = "Phường Mẫu"
    seed_ward_slug: str = "phuong-mau"

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
