from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from uuid import UUID
from app.models.organization import OrgRole
from app.schemas.user import UserResponse


class OrgCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    province_id: UUID | None = None


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    slug: str | None = Field(default=None, min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    province_id: UUID | None = None


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
    org_type: str
    province_id: UUID | None
    created_at: datetime
    updated_at: datetime
    members: list[MemberResponse] = []


class WardListItem(BaseModel):
    """Lightweight ward entry — for the citizen ward picker (no member data)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    org_type: str


class AddMemberRequest(BaseModel):
    """Assign an existing user as ward staff (always ward_officer)."""
    user_id: UUID
