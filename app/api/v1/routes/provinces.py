from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.province import Province
from app.models.user import User
from app.schemas.province import ProvinceCreate, ProvinceUpdate, ProvinceResponse
from app.core.deps import get_current_user, get_current_superuser
from app.utils.text import slugify

router = APIRouter(prefix="/provinces", tags=["Provinces"])


async def _get_or_404(province_id: UUID, db: AsyncSession) -> Province:
    province = await db.get(Province, province_id)
    if not province:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Province not found")
    return province


async def _assert_unique(db: AsyncSession, *, name: str | None, slug: str | None, exclude_id: UUID | None = None):
    conds = []
    if name is not None:
        conds.append(Province.name == name)
    if slug is not None:
        conds.append(Province.slug == slug)
    if not conds:
        return
    from sqlalchemy import or_
    q = select(Province).where(or_(*conds))
    if exclude_id is not None:
        q = q.where(Province.id != exclude_id)
    dup = (await db.execute(q)).scalars().first()
    if dup:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Province name or slug already exists")


@router.post("", response_model=ProvinceResponse, status_code=status.HTTP_201_CREATED)
async def create_province(
    body: ProvinceCreate,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Tạo tỉnh. Super_admin only."""
    slug = body.slug or slugify(body.name)
    await _assert_unique(db, name=body.name, slug=slug)
    province = Province(name=body.name, slug=slug)
    db.add(province)
    await db.flush()
    await db.refresh(province)
    return province


@router.get("", response_model=list[ProvinceResponse])
async def list_provinces(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(Province).order_by(Province.name))).scalars().all()
    return list(rows)


@router.get("/{province_id}", response_model=ProvinceResponse)
async def get_province(
    province_id: UUID,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_or_404(province_id, db)


@router.patch("/{province_id}", response_model=ProvinceResponse)
async def update_province(
    province_id: UUID,
    body: ProvinceUpdate,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Chỉnh sửa thông tin tỉnh. Super_admin only."""
    province = await _get_or_404(province_id, db)
    new_name = body.name if body.name is not None else None
    new_slug = body.slug if body.slug is not None else None
    await _assert_unique(db, name=new_name, slug=new_slug, exclude_id=province_id)
    if new_name is not None:
        province.name = new_name
    if new_slug is not None:
        province.slug = new_slug
    await db.flush()
    await db.refresh(province)
    return province


@router.delete("/{province_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_province(
    province_id: UUID,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Xoá tỉnh. Super_admin only. Organization thuộc tỉnh sẽ có province_id = NULL (FK SET NULL)."""
    province = await db.get(Province, province_id)
    if province:
        await db.delete(province)
