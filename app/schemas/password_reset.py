from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$", description="Mã OTP 6 chữ số")


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$", description="Mã OTP 6 chữ số")
    new_password: str = Field(min_length=8)


class MessageResponse(BaseModel):
    message: str
