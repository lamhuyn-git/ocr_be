from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_current_staff
from app.database import get_db
from app.models.form import Form as FormModel, FormResult
from app.models.user import User
from app.schemas.form import FormResultCreate, FormResultUpdate, FormResultResponse

router = APIRouter(prefix="/form-results", tags=["FormResult"])


@router.post("", response_model=FormResultResponse, status_code=status.HTTP_201_CREATED, summary="Create a form result (1 field)")
async def create_form_result(
    body: FormResultCreate,
    _: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    if not await db.get(FormModel, body.form_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    result = FormResult(**body.model_dump())
    db.add(result)
    await db.flush()
    await db.refresh(result)
    return result


@router.get("", response_model=list[FormResultResponse], summary="List form results (filter by form_id)")
async def list_form_results(
    form_id: UUID | None = None,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(FormResult)
    if form_id is not None:
        query = query.where(FormResult.form_id == form_id)
    rows = (await db.execute(query.order_by(FormResult.position))).scalars().all()
    return list(rows)


@router.get("/{result_id}", response_model=FormResultResponse, summary="Get a form result")
async def get_form_result(
    result_id: UUID,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.get(FormResult, result_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form result not found")
    return result


@router.patch("/{result_id}", response_model=FormResultResponse, summary="Update a form result")
async def update_form_result(
    result_id: UUID,
    body: FormResultUpdate,
    _: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.get(FormResult, result_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form result not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(result, field, value)
    await db.flush()
    await db.refresh(result)
    return result


@router.delete("/{result_id}", summary="Delete a form result")
async def delete_form_result(
    result_id: UUID,
    _: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.get(FormResult, result_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form result not found")
    await db.delete(result)
    await db.flush()
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Deleted form result successfully"})
