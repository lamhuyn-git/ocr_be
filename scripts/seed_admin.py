"""Seed initial accounts for the internal, admin-provisioned system.

Creates (idempotently, keyed by national_id / ward slug):
  1. a super_admin (is_superuser=True)
  2. a sample ward (Organization) + a ward_officer user + ward_officer membership

Run once after migrations:
    .venv/bin/python scripts/seed_admin.py

Credentials are read from settings/.env (see app/config.py: seed_* fields).
"""
from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.models.organization import Organization, OrganizationMember, OrgRole


async def _get_or_create_user(db, *, national_id, password, full_name, email, is_superuser):
    user = (
        await db.execute(select(User).where(User.national_id == national_id))
    ).scalar_one_or_none()
    if user:
        print(f"  - user {national_id} already exists ({'superuser' if user.is_superuser else 'user'}) — skip")
        return user, False
    user = User(
        national_id=national_id,
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        is_superuser=is_superuser,
    )
    db.add(user)
    await db.flush()
    print(f"  + created user {national_id} ({'superuser' if is_superuser else 'ward_officer'})")
    return user, True


async def _get_or_create_ward(db, *, name, slug):
    ward = (
        await db.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none()
    if ward:
        print(f"  - ward '{slug}' already exists — skip")
        return ward, False
    ward = Organization(name=name, slug=slug)
    db.add(ward)
    await db.flush()
    print(f"  + created ward '{slug}'")
    return ward, True


async def seed() -> None:
    s = get_settings()
    async with AsyncSessionLocal() as db:
        print("Seeding super_admin...")
        await _get_or_create_user(
            db,
            national_id=s.seed_admin_national_id,
            password=s.seed_admin_password,
            full_name=s.seed_admin_full_name,
            email=s.seed_admin_email,
            is_superuser=True,
        )

        print("Seeding sample ward + ward_officer...")
        ward, _ = await _get_or_create_ward(db, name=s.seed_ward_name, slug=s.seed_ward_slug)
        officer, _ = await _get_or_create_user(
            db,
            national_id=s.seed_ward_officer_national_id,
            password=s.seed_ward_officer_password,
            full_name=s.seed_ward_officer_full_name,
            email=None,
            is_superuser=False,
        )

        existing_member = (
            await db.execute(
                select(OrganizationMember).where(
                    OrganizationMember.org_id == ward.id,
                    OrganizationMember.user_id == officer.id,
                )
            )
        ).scalar_one_or_none()
        if existing_member:
            print("  - ward_officer membership already exists — skip")
        else:
            db.add(OrganizationMember(org_id=ward.id, user_id=officer.id, role=OrgRole.ward_officer))
            print(f"  + assigned ward_officer to ward '{ward.slug}'")

        await db.commit()

    print("\nDone. Login with CCCD:")
    print(f"  super_admin  national_id = {s.seed_admin_national_id}")
    print(f"  ward_officer national_id = {s.seed_ward_officer_national_id}")


if __name__ == "__main__":
    asyncio.run(seed())
