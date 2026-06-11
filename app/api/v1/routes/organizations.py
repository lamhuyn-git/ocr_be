from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.organization import Organization, OrganizationMember, OrgRole
from app.models.province import Province
from app.models.user import User
from app.schemas.organization import (
    OrgCreate, OrgUpdate, OrgResponse, MemberResponse, WardListItem, AddMemberRequest,
)
from app.core.deps import (
    get_current_user, get_current_superuser, require_ward_role, get_user_membership,
)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrgCreate,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Create a ward. Super_admin only."""
    existing = (await db.execute(select(Organization).where(Organization.slug == body.slug))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already taken")
    if body.province_id is not None and not await db.get(Province, body.province_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Province not found")

    org = Organization(name=body.name, slug=body.slug, province_id=body.province_id)
    db.add(org)
    await db.flush()
    await db.refresh(org)
    return org


@router.get("", response_model=list[WardListItem])
async def list_wards(
    province_id: UUID | None = None,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Organization).order_by(Organization.name)
    if province_id is not None:
        query = query.where(Organization.province_id == province_id)
    orgs = (await db.execute(query)).scalars().all()
    return list(orgs)


@router.get("/{org_id}", response_model=OrgResponse)
async def get_organization(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ward detail (incl. members). Super_admin or staff of this ward."""
    if not current_user.is_superuser:
        membership = await get_user_membership(org_id, current_user, db)
        if not membership:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.patch("/{org_id}", response_model=OrgResponse)
async def update_organization(
    org_id: UUID,
    body: OrgUpdate,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Update a ward (name / slug / province_id). Super_admin only."""
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    if body.slug is not None and body.slug != org.slug:
        dup = (
            await db.execute(
                select(Organization).where(Organization.slug == body.slug, Organization.id != org_id)
            )
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already taken")
    if body.province_id is not None and not await db.get(Province, body.province_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Province not found")

    if body.name is not None:
        org.name = body.name
    if body.slug is not None:
        org.slug = body.slug
    if body.province_id is not None:
        org.province_id = body.province_id

    await db.flush()
    await db.refresh(org)
    return org


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: UUID,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Delete a ward. Super_admin only."""
    org = await db.get(Organization, org_id)
    if org:
        await db.delete(org)


# --- Members (cán bộ phường = ward_officer). Staff management is super_admin only. ---

@router.get("/{org_id}/members", response_model=list[MemberResponse])
async def list_members(
    org_id: UUID,
    _: OrganizationMember | None = Depends(require_ward_role(OrgRole.ward_officer)),
    db: AsyncSession = Depends(get_db),
):
    """List ward staff. Super_admin or staff of this ward."""
    members = (
        await db.execute(select(OrganizationMember).where(OrganizationMember.org_id == org_id))
    ).scalars().all()
    return list(members)


@router.post("/{org_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    org_id: UUID,
    body: AddMemberRequest,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Assign a user as ward staff (ward_officer). Super_admin only."""
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    user = await db.get(User, body.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = await get_user_membership(org_id, user, db)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already a member")

    member = OrganizationMember(org_id=org_id, user_id=body.user_id, role=OrgRole.ward_officer)
    db.add(member)
    await db.flush()
    await db.refresh(member)
    return member
