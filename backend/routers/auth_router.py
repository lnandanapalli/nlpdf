"""Authentication router: signup, login, and current user."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.cookies import clear_auth_cookies, set_auth_cookies
from backend.auth.dependencies import get_current_user
from backend.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from backend.auth.password import hash_password, verify_password
from backend.crud.user_crud import (
    clear_refresh_token_jti,
    create_user,
    get_user_by_email,
    increment_otp_attempts,
    mark_user_verified,
    record_failed_login,
    reset_failed_logins,
    update_refresh_token_jti,
    update_user_otp,
)
from backend.database import get_db
from backend.models.user import User
from backend.rate_limit import limiter
from backend.schemas.auth_schema import (
    LoginRequest,
    ResendOTPRequest,
    SignupRequest,
    SuccessResponse,
    UserResponse,
    VerifyOTPRequest,
)
from backend.services.email_service import send_otp_email
from backend.services.turnstile_service import verify_turnstile

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
    if not await verify_turnstile(body.cf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CAPTCHA verification failed",
        )

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


@router.post("/verify_otp", response_model=SuccessResponse)
async def verify_otp(
    body: VerifyOTPRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> SuccessResponse:
    """Verify an OTP code, set auth cookies, and return success."""
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

    if user.otp_code is None or user.otp_expires_at is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active verification code. Please request a new one.",
        )

    if (user.otp_attempts or 0) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Please request a new code.",
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

    if user.otp_code != body.otp_code:
        await increment_otp_attempts(db, user)
        remaining = 5 - (user.otp_attempts or 0)
        if remaining <= 0:
            detail = "Too many failed attempts. Please request a new code."
        else:
            detail = "Invalid verification code"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )

    await mark_user_verified(db, user)
    access = create_access_token({"sub": user.email})
    refresh, jti = create_refresh_token({"sub": user.email})
    await update_refresh_token_jti(db, user, jti)
    set_auth_cookies(response, access, refresh)
    return SuccessResponse(message="Email verified successfully")


@router.post("/resend_otp", response_model=SuccessResponse)
@limiter.limit("3/10minutes")
async def resend_otp(
    request: Request,
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


@router.post("/login", response_model=SuccessResponse)
async def login(
    body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> SuccessResponse:
    """Authenticate a user, set auth cookies, and return success."""
    if not await verify_turnstile(body.cf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CAPTCHA verification failed",
        )

    user = await get_user_by_email(db, body.email)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Check account lockout
    if user.locked_until is not None:
        locked_until = (
            user.locked_until.replace(tzinfo=timezone.utc)
            if user.locked_until.tzinfo is None
            else user.locked_until
        )
        if locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Account temporarily locked due to too many failed "
                "login attempts. Please try again later.",
            )
        # Lock period expired — reset
        await reset_failed_logins(db, user)

    if not verify_password(body.password, str(user.hashed_password)):
        await record_failed_login(db, user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unverified email. Please verify your account.",
        )

    await reset_failed_logins(db, user)
    access = create_access_token({"sub": user.email})
    refresh, jti = create_refresh_token({"sub": user.email})
    await update_refresh_token_jti(db, user, jti)
    set_auth_cookies(response, access, refresh)
    return SuccessResponse(message="Login successful")


@router.post("/refresh", response_model=SuccessResponse)
async def refresh(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> SuccessResponse:
    """Exchange a valid refresh token cookie for a new token pair (one-time use)."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )

    try:
        payload = decode_refresh_token(refresh_token)
        email: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = await get_user_by_email(db, email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Validate JTI — reject reused tokens (one-time use)
    if jti is None or user.refresh_token_jti != jti:
        # Possible token theft — revoke all refresh tokens for this user
        await clear_refresh_token_jti(db, user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    new_access = create_access_token({"sub": email})
    new_refresh, new_jti = create_refresh_token({"sub": email})
    await update_refresh_token_jti(db, user, new_jti)
    set_auth_cookies(response, new_access, new_refresh)
    return SuccessResponse(message="Tokens refreshed")


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """Log out the current user by revoking tokens and clearing cookies."""
    await clear_refresh_token_jti(db, current_user)
    clear_auth_cookies(response)
    return SuccessResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user."""
    return UserResponse.model_validate(current_user)
