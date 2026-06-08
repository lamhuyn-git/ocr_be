from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.organization import Organization, OrganizationMember, OrgRole
from app.models.user import User
from app.schemas.organization import (
    OrgCreate, OrgUpdate, OrgResponse, MemberResponse,
    InviteMemberRequest, UpdateMemberRoleRequest,
)
from app.core.deps import get_current_user, require_org_role

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrgCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = (await db.execute(select(Organization).where(Organization.slug == body.slug))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already taken")

    org = Organization(name=body.name, slug=body.slug)
    db.add(org)
    await db.flush()

    db.add(OrganizationMember(org_id=org.id, user_id=current_user.id, role=OrgRole.owner))
    await db.flush()
    await db.refresh(org)
    return org


@router.get("", response_model=list[OrgResponse])
async def list_my_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
    _: OrganizationMember = Depends(require_org_role(OrgRole.owner, OrgRole.admin, OrgRole.member)),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.patch("/{org_id}", response_model=OrgResponse)
async def update_organization(
    org_id: UUID,
    body: OrgUpdate,
    _: OrganizationMember = Depends(require_org_role(OrgRole.owner, OrgRole.admin)),
    db: AsyncSession = Depends(get_db),
):
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
    _: OrganizationMember = Depends(require_org_role(OrgRole.owner)),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, org_id)
    if org:
        await db.delete(org)


# --- Members ---

@router.get("/{org_id}/members", response_model=list[MemberResponse])
async def list_members(
    org_id: UUID,
    _: OrganizationMember = Depends(require_org_role(OrgRole.owner, OrgRole.admin, OrgRole.member)),
    db: AsyncSession = Depends(get_db),
):
    members = (
        await db.execute(select(OrganizationMember).where(OrganizationMember.org_id == org_id))
    ).scalars().all()
    return list(members)


@router.post("/{org_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    org_id: UUID,
    body: InviteMemberRequest,
    _: OrganizationMember = Depends(require_org_role(OrgRole.owner, OrgRole.admin)),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, body.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = (
        await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.org_id == org_id,
                OrganizationMember.user_id == body.user_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already a member")

    member = OrganizationMember(org_id=org_id, user_id=body.user_id, role=body.role)
    db.add(member)
    await db.flush()
    await db.refresh(member)
    return member


@router.patch("/{org_id}/members/{user_id}", response_model=MemberResponse)
async def update_member_role(
    org_id: UUID,
    user_id: UUID,
    body: UpdateMemberRoleRequest,
    current_membership: OrganizationMember = Depends(require_org_role(OrgRole.owner, OrgRole.admin)),
    db: AsyncSession = Depends(get_db),
):
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
    # Only owner can promote/demote owner role
    if target.role == OrgRole.owner or body.role == OrgRole.owner:
        if current_membership.role != OrgRole.owner:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can manage owner role")
    target.role = body.role
    await db.flush()
    await db.refresh(target)
    return target


@router.delete("/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    current_membership: OrganizationMember = Depends(require_org_role(OrgRole.owner, OrgRole.admin)),
    db: AsyncSession = Depends(get_db),
):
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
    if target.role == OrgRole.owner:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove owner")
    await db.delete(target)
