from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.citizen import Citizen
from app.models.user import User
from app.schemas.citizen import CitizenCreate, CitizenUpdate, CitizenResponse
from app.core.deps import get_current_user, get_current_superuser

router = APIRouter(prefix="/citizens", tags=["Citizens"])


@router.post("", response_model=CitizenResponse, status_code=status.HTTP_201_CREATED, summary="Create a citizen (CSDL dân cư)")
async def create_citizen(
    body: CitizenCreate,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    existing = (
        await db.execute(select(Citizen).where(Citizen.so_dinh_danh == body.so_dinh_danh))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Citizen với số định danh này đã tồn tại")

    # Liên kết user (nếu có) phải tồn tại và chưa gắn citizen khác
    if body.user_id is not None:
        if not await db.get(User, body.user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        linked = (
            await db.execute(select(Citizen).where(Citizen.user_id == body.user_id))
        ).scalar_one_or_none()
        if linked:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="User đã gắn với một citizen khác")

    citizen = Citizen(**body.model_dump())
    db.add(citizen)
    await db.flush()
    await db.refresh(citizen)
    return citizen


@router.get("", response_model=CitizenResponse, summary="Get citizen detail")
async def get_citizen(
    citizen_id: UUID | None = None,
    user_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if citizen_id is None and user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Should provide citizen_id or user_id")

    if not current_user.is_superuser:
        if citizen_id is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        if user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    if citizen_id is not None:
        citizen = await db.get(Citizen, citizen_id)
    else:
        citizen = (
            await db.execute(select(Citizen).where(Citizen.user_id == user_id))
        ).scalar_one_or_none()

    if not citizen:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Citizen not found")

    return citizen


@router.patch("/{citizen_id}", response_model=CitizenResponse, summary="Update a citizen")
async def update_citizen(
    citizen_id: UUID,
    body: CitizenUpdate,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    citizen = await db.get(Citizen, citizen_id)
    if not citizen:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Citizen not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(citizen, field, value)
    await db.flush()
    await db.refresh(citizen)
    return citizen


@router.post("/{citizen_id}/activate", summary="Activate a citizen")
async def activate_citizen(
    citizen_id: UUID,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    citizen = await db.get(Citizen, citizen_id)
    if not citizen:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Citizen not found")
    citizen.is_active = True
    await db.flush()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Activate citizen successfully"},
    )
