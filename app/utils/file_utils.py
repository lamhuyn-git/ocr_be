from __future__ import annotations
import os
import uuid
import aiofiles
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
from app.config import get_settings

settings = get_settings()


def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


def validate_file(file: UploadFile) -> None:
    ext = get_file_extension(file.filename or "")
    if ext not in settings.allowed_ext_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '.{ext}' not allowed. Allowed: {', '.join(sorted(settings.allowed_ext_set))}",
        )


async def save_upload(file: UploadFile) -> tuple[str, str, int]:
    """Save uploaded file to disk. Returns (stored_filename, file_path, file_size)."""
    ext = get_file_extension(file.filename or "file")
    stored_filename = f"{uuid.uuid4()}.{ext}"
    file_path = os.path.join(settings.upload_dir, stored_filename)

    os.makedirs(settings.upload_dir, exist_ok=True)

    content = await file.read()
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {settings.max_file_size_mb}MB limit",
        )

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    return stored_filename, file_path, len(content)


def delete_file(file_path: str) -> None:
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass
