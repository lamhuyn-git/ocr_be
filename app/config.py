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
