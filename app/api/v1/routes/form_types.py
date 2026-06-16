from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_current_superuser
from app.database import get_db
from app.models.form import FormType
from app.models.user import User
from app.schemas.form import FormTypeCreate, FormTypeUpdate, FormTypeResponse

router = APIRouter(prefix="/form-types", tags=["FormType"])


async def _assert_name_free(db: AsyncSession, name: str, exclude_id: UUID | None = None) -> None:
    query = select(FormType).where(FormType.type_name == name)
    if exclude_id is not None:
        query = query.where(FormType.id != exclude_id)
    if (await db.execute(query)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Form type already exists")


@router.post("", response_model=FormTypeResponse, status_code=status.HTTP_201_CREATED, summary="Create a form type")
async def create_form_type(
    body: FormTypeCreate,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    name = body.type_name.strip().lower()
    await _assert_name_free(db, name)
    form_type = FormType(type_name=name)
    db.add(form_type)
    await db.flush()
    await db.refresh(form_type)
    return form_type


@router.get("", response_model=list[FormTypeResponse], summary="List all form types")
async def list_form_types(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(FormType).order_by(FormType.created_at.desc()))).scalars().all()
    return list(rows)


@router.get("/{form_type_id}", response_model=FormTypeResponse, summary="Get a form type")
async def get_form_type(
    form_type_id: UUID,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    form_type = await db.get(FormType, form_type_id)
    if not form_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form type not found")
    return form_type


@router.patch("/{form_type_id}", response_model=FormTypeResponse, summary="Update a form type")
async def update_form_type(
    form_type_id: UUID,
    body: FormTypeUpdate,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    form_type = await db.get(FormType, form_type_id)
    if not form_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form type not found")
    name = body.type_name.strip().lower()
    await _assert_name_free(db, name, exclude_id=form_type_id)
    form_type.type_name = name
    await db.flush()
    await db.refresh(form_type)
    return form_type


@router.delete("/{form_type_id}", summary="Delete a form type")
async def delete_form_type(
    form_type_id: UUID,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    form_type = await db.get(FormType, form_type_id)
    if not form_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form type not found")
    await db.delete(form_type)
    await db.flush()
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Deleted form type successfully"})
