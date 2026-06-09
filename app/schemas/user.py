from __future__ import annotations
from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from uuid import UUID


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    national_id: str | None
    email: str | None
    full_name: str | None
    role: str | None = None       # super_admin | ward_officer | citizen (set by /me)
    is_active: bool
    is_superuser: bool
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None


class UserAdminUpdate(UserUpdate):
    is_active: bool | None = None
    is_superuser: bool | None = None
