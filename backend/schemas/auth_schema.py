"""Request/response schemas for authentication."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    """User registration request."""

    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    cf_token: str = Field(..., max_length=4096)


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., max_length=128)
    cf_token: str = Field(..., max_length=4096)


class UserResponse(BaseModel):
    """Public user information."""

    id: int
    email: str
    first_name: str | None = None
    last_name: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class VerifyOTPRequest(BaseModel):
    """Request to verify an OTP."""

    email: EmailStr = Field(..., max_length=255)
    otp_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    cf_token: str = Field(..., max_length=4096)


class ResendOTPRequest(BaseModel):
    """Request to resend an OTP to an unverified email."""

    email: EmailStr = Field(..., max_length=255)


class SuccessResponse(BaseModel):
    """Generic success message response."""

    message: str


class UpdateProfileRequest(BaseModel):
    """Request to update user profile (name)."""

    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)


class ChangePasswordRequest(BaseModel):
    """Request to change password."""

    current_password: str = Field(..., max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class DeleteAccountRequest(BaseModel):
    """Request to initiate account deletion (step 1: verify password, send OTP)."""

    password: str = Field(..., max_length=128)


class DeleteAccountConfirmRequest(BaseModel):
    """Request to confirm account deletion (step 2: verify OTP)."""

    otp_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class ForgotPasswordRequest(BaseModel):
    """Request to initiate password reset."""

    email: EmailStr = Field(..., max_length=255)
    cf_token: str = Field(..., max_length=4096)


class ResetPasswordRequest(BaseModel):
    """Request to complete password reset."""

    email: EmailStr = Field(..., max_length=255)
    otp_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(..., min_length=8, max_length=128)
    cf_token: str = Field(..., max_length=4096)


class SessionResponse(BaseModel):
    """A single active login session — shown in the 'Active Sessions' settings page."""

    id: int
    ip_address: str | None = None
    device_name: str | None = None
    browser: str | None = None
    os: str | None = None
    is_mobile: bool = False
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    is_current: bool = False  # True when this session matches the caller's session_id

    model_config = {"from_attributes": True}
