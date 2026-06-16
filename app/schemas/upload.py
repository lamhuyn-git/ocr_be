from __future__ import annotations

from pydantic import BaseModel, Field


class PresignRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    kind: str = Field(default="FILE", max_length=50)  # hint loại ảnh (vd CT01) → prefix key


class PresignResponse(BaseModel):
    upload_url: str  # URL ký sẵn để FE PUT file lên S3
    file_url: str    # URL định danh ảnh sau upload → dùng làm path_url


class ViewUrlRequest(BaseModel):
    path_url: str = Field(min_length=1, max_length=512)  # file_url đã lưu


class ViewUrlResponse(BaseModel):
    url: str  # URL ký sẵn để xem ảnh (hết hạn sau presign_expire)
