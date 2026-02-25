"""Authentication router: signup, login, and current user."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.auth.jwt import create_access_token
from backend.auth.password import hash_password, verify_password
from backend.crud.user_crud import (
    create_user,
    get_user_by_email,
    mark_user_verified,
    update_user_otp,
)
from backend.database import get_db
from backend.models.user import User
from backend.schemas.auth_schema import (
    LoginRequest,
    ResendOTPRequest,
    SignupRequest,
    SuccessResponse,
    TokenResponse,
    UserResponse,
    VerifyOTPRequest,
)
from backend.services.email_service import send_otp_email

router = APIRouter(prefix="/auth", tags=["auth"])


def generate_otp() -> str:
    """Generate a cryptographically secure random 6-digit OTP."""
    return str(secrets.randbelow(900000) + 100000)


@router.post("/signup", response_model=SuccessResponse, status_code=201)
async def signup(
    body: SignupRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """Register a new user and return success message requiring OTP verification."""
    existing = await get_user_by_email(db, body.email)

    if existing is not None:
        if existing.is_verified:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )
        else:
            # Reusing unverified account
            hashed = hash_password(body.password)
            existing.hashed_password = hashed
            await db.commit()
            user = existing
    else:
        hashed = hash_password(body.password)
        user = await create_user(db, body.email, hashed)

    otp_code = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    await update_user_otp(db, user, otp_code, expires_at)

    background_tasks.add_task(send_otp_email, str(user.email), otp_code)

    return SuccessResponse(message="Verification code sent to email")


@router.post("/verify_otp", response_model=TokenResponse)
async def verify_otp(
    body: VerifyOTPRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Verify an OTP code and return a JWT."""
    user = await get_user_by_email(db, body.email)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is already verified",
        )

    if user.otp_code != body.otp_code:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code",
        )

    if user.otp_expires_at is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verification code has expired",
        )

    expires_at = (
        user.otp_expires_at.replace(tzinfo=timezone.utc)
        if user.otp_expires_at.tzinfo is None
        else user.otp_expires_at
    )
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verification code has expired",
        )

    await mark_user_verified(db, user)
    token = create_access_token({"sub": user.email})
    return TokenResponse(access_token=token)


@router.post("/resend_otp", response_model=SuccessResponse)
async def resend_otp(
    body: ResendOTPRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """Generate and send a new OTP code to an unverified email."""
    user = await get_user_by_email(db, body.email)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is already verified",
        )

    otp_code = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    await update_user_otp(db, user, otp_code, expires_at)
    background_tasks.add_task(send_otp_email, str(user.email), otp_code)

    return SuccessResponse(message="Verification code resent to email")


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Authenticate a user and return a JWT."""
    user = await get_user_by_email(db, body.email)

    if user is None or not verify_password(body.password, str(user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unverified email. Please verify your account.",
        )

    token = create_access_token({"sub": user.email})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user."""
    return UserResponse.model_validate(current_user)
