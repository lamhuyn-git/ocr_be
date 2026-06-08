from __future__ import annotations
import asyncio
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.ocr import OcrJob, JobStatus
from app.models.user import User
from app.schemas.ocr import OcrJobResponse, OcrJobList, OcrProcessResponse, FormDataUpdate
from app.utils.file_utils import validate_file, save_upload, delete_file, get_file_extension
from app.services.ocr_service import run_ocr
from app.core.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ocr", tags=["OCR"])

MIME_MAP = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "bmp": "image/bmp", "tiff": "image/tiff", "webp": "image/webp",
    "pdf": "application/pdf",
}


async def _run_ocr_background(job_id: UUID, file_path: str, lang: str) -> None:
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        job = await db.get(OcrJob, job_id)
        if not job:
            return
        job.status = JobStatus.processing
        await db.commit()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, run_ocr, file_path, lang)
            job.extracted_text = result["extracted_text"]
            job.confidence_score = result["confidence_score"]
            job.ocr_result = {"pages": result["pages"]}
            job.page_count = result["page_count"]
            job.processing_time_ms = result["processing_time_ms"]
            job.status = JobStatus.completed
        except Exception as exc:
            logger.exception("OCR job %s failed", job_id)
            job.status = JobStatus.failed
            job.error_message = str(exc)

        await db.commit()


@router.post("/upload", response_model=OcrProcessResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_and_process(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Form(default="en"),
    org_id: UUID | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file and start OCR processing asynchronously."""
    validate_file(file)
    stored_filename, file_path, file_size = await save_upload(file)
    ext = get_file_extension(file.filename or "file")
    mime_type = MIME_MAP.get(ext, "application/octet-stream")

    job = OcrJob(
        filename=stored_filename,
        original_filename=file.filename or stored_filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=mime_type,
        language=language,
        org_id=org_id,
        created_by=current_user.id,
        status=JobStatus.pending,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    job_id = job.id

    background_tasks.add_task(_run_ocr_background, job_id, file_path, language)

    return OcrProcessResponse(job_id=job_id, status=JobStatus.pending,
                              message="File uploaded. OCR processing started.")


@router.post("/process-sync", response_model=OcrJobResponse)
async def upload_and_process_sync(
    file: UploadFile = File(...),
    language: str = Form(default="en"),
    org_id: UUID | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload + process synchronously. Returns full result immediately."""
    validate_file(file)
    stored_filename, file_path, file_size = await save_upload(file)
    ext = get_file_extension(file.filename or "file")
    mime_type = MIME_MAP.get(ext, "application/octet-stream")

    job = OcrJob(
        filename=stored_filename,
        original_filename=file.filename or stored_filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=mime_type,
        language=language,
        org_id=org_id,
        created_by=current_user.id,
        status=JobStatus.processing,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_ocr, file_path, language)
        job.extracted_text = result["extracted_text"]
        job.confidence_score = result["confidence_score"]
        job.ocr_result = {"pages": result["pages"]}
        job.page_count = result["page_count"]
        job.processing_time_ms = result["processing_time_ms"]
        job.status = JobStatus.completed
    except Exception as exc:
        logger.exception("Sync OCR failed for job %s", job.id)
        job.status = JobStatus.failed
        job.error_message = str(exc)

    await db.flush()
    await db.refresh(job)
    return job


@router.get("/jobs", response_model=OcrJobList)
async def list_jobs(
    page: int = 1,
    page_size: int = 20,
    status_filter: JobStatus | None = None,
    org_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = select(OcrJob)
    count_query = select(func.count()).select_from(OcrJob)

    # Non-superusers see only their own jobs (or org jobs if org_id given)
    if not current_user.is_superuser:
        query = query.where(OcrJob.created_by == current_user.id)
        count_query = count_query.where(OcrJob.created_by == current_user.id)

    if status_filter:
        query = query.where(OcrJob.status == status_filter)
        count_query = count_query.where(OcrJob.status == status_filter)
    if org_id:
        query = query.where(OcrJob.org_id == org_id)
        count_query = count_query.where(OcrJob.org_id == org_id)

    total = (await db.execute(count_query)).scalar_one()
    jobs = (
        await db.execute(
            query.order_by(OcrJob.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return OcrJobList(total=total, page=page, page_size=page_size, items=list(jobs))


@router.get("/jobs/{job_id}", response_model=OcrJobResponse)
async def get_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(OcrJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not current_user.is_superuser and job.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return job


@router.put("/jobs/{job_id}/form", response_model=OcrJobResponse)
async def update_form(
    job_id: UUID,
    body: FormDataUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save reviewed/edited form fields for an OCR job."""
    job = await db.get(OcrJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not current_user.is_superuser and job.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if job.status != JobStatus.completed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="OCR must be completed before submitting form")

    job.form_data = body.fields
    job.form_confirmed = body.confirmed
    await db.flush()
    await db.refresh(job)
    return job


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(OcrJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not current_user.is_superuser and job.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    delete_file(job.file_path)
    await db.delete(job)
