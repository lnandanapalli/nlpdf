"""Request/response schemas for authentication."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user information."""

    id: int
    email: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class VerifyOTPRequest(BaseModel):
    """Request to verify an OTP."""

    email: EmailStr
    otp_code: str


class ResendOTPRequest(BaseModel):
    """Request to resend an OTP to an unverified email."""

    email: EmailStr


class SuccessResponse(BaseModel):
    """Generic success message response."""

    message: str
