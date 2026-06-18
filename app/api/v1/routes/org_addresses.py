from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.org_address import OrgAddress
from app.models.organization import Organization
from app.models.user import User
from app.schemas.org_address import OrgAddressCreate, OrgAddressUpdate, OrgAddressResponse
from app.core.deps import get_current_superuser

router = APIRouter(prefix="/org-addresses", tags=["OrgAddress"])


async def _get_or_404(addr_id: UUID, db: AsyncSession) -> OrgAddress:
    addr = await db.get(OrgAddress, addr_id)
    if not addr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org address not found")
    return addr


async def _assert_org_exists(db: AsyncSession, org_id: UUID) -> None:
    if not await db.get(Organization, org_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")


@router.post("", response_model=OrgAddressResponse, status_code=status.HTTP_201_CREATED)
async def create_org_address(
    body: OrgAddressCreate,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Tạo địa chỉ do phường quản lý. Super_admin only."""
    await _assert_org_exists(db, body.org_id)
    addr = OrgAddress(org_id=body.org_id, dia_chi=body.dia_chi, is_active=body.is_active)
    db.add(addr)
    await db.flush()
    await db.refresh(addr)
    return addr


@router.get("", response_model=list[OrgAddressResponse])
async def list_org_addresses(
    org_id: UUID | None = Query(default=None, description="Lọc theo phường"),
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Danh sách địa chỉ phường quản lý. Super_admin only."""
    q = select(OrgAddress).order_by(OrgAddress.created_at.desc())
    if org_id is not None:
        q = q.where(OrgAddress.org_id == org_id)
    rows = (await db.execute(q)).scalars().all()
    return list(rows)


@router.get("/{addr_id}", response_model=OrgAddressResponse)
async def get_org_address(
    addr_id: UUID,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    return await _get_or_404(addr_id, db)


@router.patch("/{addr_id}", response_model=OrgAddressResponse)
async def update_org_address(
    addr_id: UUID,
    body: OrgAddressUpdate,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Chỉnh sửa địa chỉ phường quản lý. Super_admin only."""
    addr = await _get_or_404(addr_id, db)
    if body.org_id is not None:
        await _assert_org_exists(db, body.org_id)
        addr.org_id = body.org_id
    if body.dia_chi is not None:
        addr.dia_chi = body.dia_chi
    if body.is_active is not None:
        addr.is_active = body.is_active
    await db.flush()
    await db.refresh(addr)
    return addr


@router.delete("/{addr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org_address(
    addr_id: UUID,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Xoá địa chỉ phường quản lý. Super_admin only."""
    addr = await db.get(OrgAddress, addr_id)
    if addr:
        await db.delete(addr)
