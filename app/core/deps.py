from __future__ import annotations
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt

from app.database import get_db
from app.models.user import User
from app.models.organization import OrganizationMember, OrgRole
from app.core.security import decode_token

bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise credentials_exception
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = await db.get(User, UUID(user_id))
    if not user or not user.is_active:
        raise credentials_exception
    return user


async def get_current_superuser(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser required")
    return current_user


async def get_user_role(user: User, db: AsyncSession) -> str:
    """Derived role for the 3-tier model: super_admin > ward_officer > citizen."""
    if user.is_superuser:
        return "super_admin"
    ward_ids = await get_user_ward_ids(user, db)
    return "ward_officer" if ward_ids else "citizen"


async def get_user_ward_ids(user: User, db: AsyncSession) -> list[UUID]:
    """Ward (organization) ids the user is a staff member of."""
    rows = (
        await db.execute(
            select(OrganizationMember.org_id).where(OrganizationMember.user_id == user.id)
        )
    ).scalars().all()
    return list(rows)


async def get_user_membership(
    org_id: UUID, user: User, db: AsyncSession
) -> OrganizationMember | None:
    return (
        await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.org_id == org_id,
                OrganizationMember.user_id == user.id,
            )
        )
    ).scalar_one_or_none()


def require_ward_role(*roles: OrgRole):
    """Dependency factory — super_admin bypasses; otherwise user must hold one of
    the given roles in the ward (`org_id` path/query param).
    Returns the membership, or None when the caller is a super_admin."""
    async def check(
        org_id: UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> OrganizationMember | None:
        if current_user.is_superuser:
            return None
        membership = await get_user_membership(org_id, current_user, db)
        if not membership:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
        if membership.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return membership

    return check


async def assert_form_ward_access(form, current_user: User, db: AsyncSession) -> None:
    """Allow access to a form if: super_admin, the submitting citizen, or staff of the form's ward."""
    if current_user.is_superuser:
        return
    if form.created_by == current_user.id:
        return
    if form.org_id is not None:
        membership = await get_user_membership(form.org_id, current_user, db)
        if membership:
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
