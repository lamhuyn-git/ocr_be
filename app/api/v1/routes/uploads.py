from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.upload import (
    PresignRequest, PresignResponse, ViewUrlRequest, ViewUrlResponse,
)
from app.services import s3_service

router = APIRouter(prefix="/uploads", tags=["Upload"])


@router.post("/presign", response_model=PresignResponse, summary="Tạo presigned URL để upload ảnh lên S3")
async def presign_upload(body: PresignRequest, _: User = Depends(get_current_user),):
    key = s3_service.build_object_key(body.filename, body.kind)
    upload_url = s3_service.generate_presigned_put(key, body.content_type) #URL có chữ ký để đẩy lên server
    return PresignResponse(upload_url=upload_url, file_url=s3_service.public_url(key))


@router.post("/view-url", response_model=ViewUrlResponse, summary="Tạo presigned URL để xem ảnh (bucket private)")
async def presign_view(
    body: ViewUrlRequest,
    _: User = Depends(get_current_user),
):
    # Suy ngược object key từ path_url đã lưu → presigned GET URL tạm thời.
    key = s3_service.key_from_path_url(body.path_url)
    return ViewUrlResponse(url=s3_service.generate_presigned_get(key))
