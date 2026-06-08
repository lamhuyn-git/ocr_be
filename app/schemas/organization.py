from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from uuid import UUID
from app.models.organization import OrgRole
from app.schemas.user import UserResponse


class OrgCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    role: OrgRole
    created_at: datetime
    user: UserResponse | None = None


class OrgResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime
    members: list[MemberResponse] = []


class InviteMemberRequest(BaseModel):
    user_id: UUID
    role: OrgRole = OrgRole.member


class UpdateMemberRoleRequest(BaseModel):
    role: OrgRole
