from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_current_staff
from app.database import get_db
from app.models.form import Form as FormModel, Evidence
from app.models.user import User
from app.schemas.form import EvidenceCreate, EvidenceUpdate, EvidenceResponse

router = APIRouter(prefix="/evidences", tags=["Evidence"])


@router.post("", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED, summary="Create an evidence (file đính kèm)")
async def create_evidence(
    body: EvidenceCreate,
    _: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    if not await db.get(FormModel, body.form_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    evidence = Evidence(**body.model_dump())
    db.add(evidence)
    await db.flush()
    await db.refresh(evidence)
    return evidence


@router.get("", response_model=list[EvidenceResponse], summary="List evidences (filter by form_id)")
async def list_evidences(
    form_id: UUID | None = None,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Evidence)
    if form_id is not None:
        query = query.where(Evidence.form_id == form_id)
    rows = (await db.execute(query.order_by(Evidence.created_at))).scalars().all()
    return list(rows)


@router.get("/{evidence_id}", response_model=EvidenceResponse, summary="Get an evidence")
async def get_evidence(
    evidence_id: UUID,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    evidence = await db.get(Evidence, evidence_id)
    if not evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    return evidence


@router.patch("/{evidence_id}", response_model=EvidenceResponse, summary="Update an evidence")
async def update_evidence(
    evidence_id: UUID,
    body: EvidenceUpdate,
    _: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    evidence = await db.get(Evidence, evidence_id)
    if not evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(evidence, field, value)
    await db.flush()
    await db.refresh(evidence)
    return evidence


@router.delete("/{evidence_id}", summary="Delete an evidence")
async def delete_evidence(
    evidence_id: UUID,
    _: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    evidence = await db.get(Evidence, evidence_id)
    if not evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    await db.delete(evidence)
    await db.flush()
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Deleted evidence successfully"})
