from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict
from typing import Any
from datetime import datetime
from uuid import UUID
from app.models.ocr import JobStatus


class OcrJobCreate(BaseModel):
    language: str = Field(default="en", description="OCR language code (en, vi, ch, etc.)")


class OcrResultWord(BaseModel):
    text: str
    confidence: float
    bbox: list[list[float]]


class OcrResultPage(BaseModel):
    page: int
    words: list[OcrResultWord]
    text: str


class FormDataUpdate(BaseModel):
    fields: dict[str, Any] = Field(description="Key-value pairs of extracted/reviewed fields")
    confirmed: bool = Field(default=False, description="Mark form as confirmed by user")


class OcrJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID | None
    created_by: UUID | None
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    page_count: int
    status: JobStatus
    language: str
    extracted_text: str | None
    confidence_score: float | None
    ocr_result: Any | None
    form_data: Any | None
    form_confirmed: Any | None
    error_message: str | None
    processing_time_ms: int | None
    created_at: datetime
    updated_at: datetime


class OcrJobList(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[OcrJobResponse]


class OcrProcessResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    message: str
