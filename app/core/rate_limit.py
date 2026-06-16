from __future__ import annotations
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()

# key_func=get_remote_address → rate-limit theo IP client.
# storage_uri: memory:// (1 worker) — đổi sang redis://... khi scale nhiều worker.
# Lưu ý: sau reverse-proxy cần cấu hình lấy IP thật từ X-Forwarded-For.
# enabled=False (dev) → bỏ qua mọi giới hạn, không trả 429.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.ratelimit_storage_uri,
    enabled=settings.ratelimit_enabled,
)
