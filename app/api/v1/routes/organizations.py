"""
/api/v1/organizations — Ward (phường) management.

Roles (3-tier):
- super_admin (is_superuser): create/update/delete wards, assign/remove staff, see everything.
- ward_officer: staff that processes/reviews forms of own ward(s).
- citizen (no membership): may LIST wards (to pick one when submitting a form).
"""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.organization import Organization, OrganizationMember, OrgRole
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

    org = Organization(name=body.name, slug=body.slug)
    db.add(org)
    await db.flush()
    await db.refresh(org)
    return org


@router.get("", response_model=list[WardListItem])
async def list_wards(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all wards (lightweight). Any authenticated user — citizens use this to pick a ward."""
    orgs = (
        await db.execute(select(Organization).order_by(Organization.name))
    ).scalars().all()
    return list(orgs)


@router.get("/mine", response_model=list[OrgResponse])
async def list_my_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Wards the current user is a staff member of (ward_officer)."""
    memberships = (
        await db.execute(
            select(OrganizationMember).where(OrganizationMember.user_id == current_user.id)
        )
    ).scalars().all()
    org_ids = [m.org_id for m in memberships]
    if not org_ids:
        return []
    orgs = (await db.execute(select(Organization).where(Organization.id.in_(org_ids)))).scalars().all()
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
    """Update a ward. Super_admin only."""
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if body.name is not None:
        org.name = body.name
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


@router.delete("/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Remove ward staff. Super_admin only."""
    target = (
        await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.org_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    await db.delete(target)
