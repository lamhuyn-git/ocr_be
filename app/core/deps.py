from __future__ import annotations
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt

from app.database import get_db
from app.models.user import User
from app.models.organization import Organization, OrganizationMember, OrgRole
from app.models.province import Province
from app.core.security import decode_token


bearer = HTTPBearer()


async def get_user_role(user: User, db: AsyncSession) -> str:
    if user.is_superuser:
        return "super_admin"
    ward_ids = await get_user_ward_ids(user, db)
    return "ward_officer" if ward_ids else "citizen"


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"},)
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


async def get_current_staff(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> User:
    if current_user.is_superuser:
        return current_user
    has_membership = (
        await db.execute(select(OrganizationMember.id).where(OrganizationMember.user_id == current_user.id).limit(1))
    ).scalar_one_or_none()
    if not has_membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff access required")
    return current_user


# Lấy phường của staff
async def get_user_ward_ids(user: User, db: AsyncSession) -> list[UUID]:
    rows = (
        await db.execute(select(OrganizationMember.org_id).where(OrganizationMember.user_id == user.id))
    ).scalars().all()
    return list(rows)


# Phường primary của officer (membership sớm nhất) + tên tỉnh, dùng prefill form.
async def get_user_primary_ward(user: User, db: AsyncSession) -> dict | None:
    row = (
        await db.execute(
            select(Organization, Province.name)
            .join(OrganizationMember, OrganizationMember.org_id == Organization.id)
            .outerjoin(Province, Province.id == Organization.province_id)
            .where(OrganizationMember.user_id == user.id)
            .order_by(OrganizationMember.created_at)
            .limit(1)
        )
    ).first()
    if not row:
        return None
    org, province_name = row
    return {
        "org_id": org.id,
        "ward_name": org.name,
        "province_id": org.province_id,
        "province_name": province_name,
    }


# Check user có là thành viên của ward (org) không
async def get_user_membership(org_id: UUID, user: User, db: AsyncSession) -> OrganizationMember | None:
    return (
        await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.org_id == org_id,
                OrganizationMember.user_id == user.id,
            )
        )
    ).scalar_one_or_none()


def require_ward_role(*roles: OrgRole):
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


# Chỉ super_admin, user upload form đó và cán bộ phường tiếp nhận đơn là được xem form
async def assert_form_ward_access(form, current_user: User, db: AsyncSession) -> None:
    if current_user.is_superuser:
        return
    if form.submit_by == current_user.id:
        return
    if form.org_id is not None:
        membership = await get_user_membership(form.org_id, current_user, db)
        if membership:
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
