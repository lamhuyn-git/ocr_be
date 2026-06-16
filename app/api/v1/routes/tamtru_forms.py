from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_current_staff
from app.database import get_db
from app.models.form import Form as FormModel, TamtruForm
from app.models.user import User
from app.schemas.form import TamtruFormCreate, TamtruFormUpdate, TamtruFormResponse

router = APIRouter(prefix="/tamtru-forms", tags=["TamtruForm"])


@router.post("", response_model=TamtruFormResponse, status_code=status.HTTP_201_CREATED, summary="Create a tamtru form (bảng con)")
async def create_tamtru_form(
    body: TamtruFormCreate,
    _: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    if not await db.get(FormModel, body.form_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    # 1:1 — mỗi form chỉ một tamtru_form
    existing = (
        await db.execute(select(TamtruForm).where(TamtruForm.form_id == body.form_id))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tamtru form already exists for this form")

    tamtru = TamtruForm(**body.model_dump())
    db.add(tamtru)
    await db.flush()
    await db.refresh(tamtru)
    return tamtru


@router.get("", response_model=list[TamtruFormResponse], summary="List tamtru forms (filter by form_id)")
async def list_tamtru_forms(
    form_id: UUID | None = None,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(TamtruForm)
    if form_id is not None:
        query = query.where(TamtruForm.form_id == form_id)
    rows = (await db.execute(query.order_by(TamtruForm.created_at.desc()))).scalars().all()
    return list(rows)


@router.get("/{tamtru_id}", response_model=TamtruFormResponse, summary="Get a tamtru form")
async def get_tamtru_form(
    tamtru_id: UUID,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tamtru = await db.get(TamtruForm, tamtru_id)
    if not tamtru:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tamtru form not found")
    return tamtru


@router.patch("/{tamtru_id}", response_model=TamtruFormResponse, summary="Update a tamtru form")
async def update_tamtru_form(
    tamtru_id: UUID,
    body: TamtruFormUpdate,
    _: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    tamtru = await db.get(TamtruForm, tamtru_id)
    if not tamtru:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tamtru form not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tamtru, field, value)
    await db.flush()
    await db.refresh(tamtru)
    return tamtru


@router.delete("/{tamtru_id}", summary="Delete a tamtru form")
async def delete_tamtru_form(
    tamtru_id: UUID,
    _: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    tamtru = await db.get(TamtruForm, tamtru_id)
    if not tamtru:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tamtru form not found")
    await db.delete(tamtru)
    await db.flush()
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Deleted tamtru form successfully"})
