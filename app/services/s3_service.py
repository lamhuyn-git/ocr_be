"""S3/MinIO storage cho luồng upload presigned.

FE xin presigned PUT URL → PUT ảnh thẳng lên S3 → lưu file_url làm path_url.
Khi chạy OCR, BE tải ảnh từ S3 về file tạm (pipeline đọc từ disk).
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _client():
    if not settings.s3_bucket:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="S3 storage chưa được cấu hình (thiếu S3_BUCKET).",
        )
    addressing = "path" if settings.s3_use_path_style else "auto"
    # Ép endpoint theo vùng để presigned URL có host vùng ngay từ đầu
    # (tránh S3 trả 307 redirect global -> regional làm hỏng CORS + chữ ký).
    endpoint = settings.s3_endpoint_url or (
        f"https://s3.{settings.aws_region}.amazonaws.com"
        if settings.aws_region
        else None
    )
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=settings.aws_region or None,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        config=Config(signature_version="s3v4", s3={"addressing_style": addressing}),
    )

def _safe_kind(kind: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", kind or "").upper()
    return cleaned or "FILE"


# Quy tắc đặt tên key: {kind}_{submit_at}_{suffix}{ext}
def build_object_key(filename: str, kind: str) -> str:
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    submit_at = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid4().hex[:8]
    return f"evidences/{_safe_kind(kind)}_{submit_at}_{suffix}{ext}"

# Setting url FE truyền cho BE
def public_url(key: str) -> str:
    if settings.s3_public_url_base:
        return f"{settings.s3_public_url_base.rstrip('/')}/{key}"
    if settings.s3_endpoint_url: 
        return f"{settings.s3_endpoint_url.rstrip('/')}/{settings.s3_bucket}/{key}"
    return f"https://{settings.s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"


def generate_presigned_put(key: str, content_type: str) -> str:
    try:
        return _client().generate_presigned_url(
            "put_object",
            Params={"Bucket": settings.s3_bucket, "Key": key, "ContentType": content_type}, #upload vào bucket nào và lưu với tên (key) nào và loại data được lưu là gì
            ExpiresIn=settings.s3_presign_expire_seconds, # presigned_url có chu kỳ sống là bao lâu
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("presign PUT failed key=%s", key)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không tạo được URL upload.",
        ) from exc


def generate_presigned_get(key: str) -> str:
    """URL ký sẵn để XEM/tải ảnh từ bucket private (hết hạn sau presign_expire)."""
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key}, 
            ExpiresIn=settings.s3_presign_expire_seconds,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("presign GET failed key=%s", key)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không tạo được URL xem ảnh.",
        ) from exc


def key_from_path_url(path_url: str) -> str:
    """path_url có thể là full URL (public_url) hoặc key thuần → trả về object key."""
    if "://" not in path_url:
        return path_url.lstrip("/")
    path = urlparse(path_url).path.lstrip("/")
    prefix = f"{settings.s3_bucket}/"
    if path.startswith(prefix):  # path-style: bucket nằm đầu path
        path = path[len(prefix):]
    return path


def download_to_temp(path_url: str) -> str:
    """Tải object S3 về file tạm, trả về đường dẫn local (caller tự xoá sau khi dùng)."""
    key = key_from_path_url(path_url)
    ext = os.path.splitext(key)[1] or ".img"
    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    try:
        _client().download_file(settings.s3_bucket, key, tmp_path)
    except (BotoCoreError, ClientError) as exc:
        logger.exception("download S3 failed key=%s", key)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không tải được ảnh từ S3.",
        ) from exc
    return tmp_path
