from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    national_id: str = Field(pattern=r"^\d{12}$", description="CCCD — 12 chữ số")
    password: str = Field(min_length=8)
    full_name: str | None = None
    email: EmailStr | None = None


class LoginRequest(BaseModel):
    """Citizen login — by CCCD."""
    national_id: str = Field(pattern=r"^\d{12}$", description="CCCD — 12 chữ số")
    password: str


class StaffLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
