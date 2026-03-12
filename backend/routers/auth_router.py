"""Authentication router: signup, login, sessions, and account management."""

from datetime import UTC, datetime, timedelta
import hmac
import secrets
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.auth.cookies import clear_auth_cookies, set_auth_cookies
from backend.auth.dependencies import get_current_session_id, get_current_user
from backend.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from backend.auth.password import DUMMY_HASH, hash_password, verify_password
from backend.config import settings
from backend.crud.session_crud import (
    SessionCreate,
    create_session,
    delete_all_user_sessions,
    delete_session_by_id,
    delete_session_by_jti,
    get_active_sessions_for_user,
    get_session_by_jti,
    rotate_session_jti,
)
from backend.crud.user_crud import (
    MAX_OTP_ATTEMPTS,
    bump_token_version,
    create_user,
    delete_user,
    get_user_by_email,
    increment_otp_attempts,
    mark_user_verified,
    record_failed_login,
    reset_failed_logins,
    update_user_name,
    update_user_otp,
    update_user_password,
)
from backend.database import get_db
from backend.models.user import User
from backend.rate_limit import limiter
from backend.schemas.auth_schema import (
    ChangePasswordRequest,
    DeleteAccountConfirmRequest,
    DeleteAccountRequest,
    LoginRequest,
    ResendOTPRequest,
    SessionResponse,
    SignupRequest,
    SuccessResponse,
    UpdateProfileRequest,
    UserResponse,
    VerifyOTPRequest,
)
from backend.security import get_client_ip, parse_device_info
from backend.services.email_service import (
    send_account_deletion_otp_email,
    send_otp_email,
)
from backend.services.turnstile_service import verify_turnstile

logger = structlog.get_logger("nlpdf.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Dependency type aliases — modern FastAPI Annotated pattern (FAST001)
# ---------------------------------------------------------------------------

DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentSessionId = Annotated[int | None, Depends(get_current_session_id)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def generate_otp() -> str:
    """Generate a cryptographically secure random 6-digit OTP."""
    return str(secrets.randbelow(900000) + 100000)


def _session_expires_at() -> datetime:
    """Compute the refresh token / session expiry datetime."""
    return datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)


def _normalize_tz(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware, assuming UTC if naive."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _validate_refresh_payload(payload: dict[str, Any]) -> tuple[str, str]:
    """Extract and validate sub and jti claims from a decoded token payload.

    Raises:
        ValueError: If either claim is missing.
    """
    email: str | None = payload.get("sub")
    jti: str | None = payload.get("jti")
    if not email or not jti:
        raise ValueError("Missing claims")
    return email, jti


async def _create_token_pair_and_session(
    db: AsyncSession,
    user: User,
    request: Request,
    response: Response,
) -> None:
    """Issue a new access+refresh token pair, record a session row, and set cookies.

    Order matters:
      1. Create refresh token first (to get the JTI)
      2. Flush session to get session.id
      3. Create access token embedding both token_version and session_id
      4. Set cookies
    """
    # 1. Refresh token (has JTI)
    refresh, jti = create_refresh_token({"sub": user.email})
    expires_at = _session_expires_at()

    # 2. Session row
    ua_string = request.headers.get("User-Agent", "")
    device = parse_device_info(ua_string)
    ip = get_client_ip(request)

    sess = await create_session(
        db=db,
        data=SessionCreate(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at,
            ip_address=ip,
            device_name=device["device_name"],
            browser=device["browser"],
            os=device["os"],
            is_mobile=device["is_mobile"],
            user_agent=ua_string[:512],
        ),
    )

    # 3. Access token — embeds token_version (C3) and session_id (for sessions list)
    access = create_access_token(
        {
            "sub": user.email,
            "ver": user.token_version or 0,
            "sid": sess.id,
        }
    )

    # 4. Set cookies
    set_auth_cookies(response, access, refresh)


def _check_otp_expiry(otp_expires_at: datetime) -> None:
    """Raise HTTP 401 if the OTP has expired."""
    if _normalize_tz(otp_expires_at) < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verification code has expired",
        )


# ---------------------------------------------------------------------------
# Signup / OTP verification
# ---------------------------------------------------------------------------


@router.post("/signup", status_code=201)
async def signup(
    body: SignupRequest,
    background_tasks: BackgroundTasks,
    db: DB,
) -> SuccessResponse:
    """Register a new user and send an OTP verification email."""
    if not await verify_turnstile(body.cf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CAPTCHA verification failed",
        )

    existing = await get_user_by_email(db, body.email)

    if existing is not None:
        if existing.is_verified:
            # Prevent email enumeration by returning generic success immediately
            return SuccessResponse(
                message="If that email is valid, a verification code has been sent."
            )

        # SECURE: Do absolutely nothing to the user's profile or password.
        # Only reuse the slot to regenerate a fresh token and resend the email.
        user = existing
    else:
        user = await create_user(
            db,
            body.email,
            hash_password(body.password),
            body.first_name,
            body.last_name,
        )

    otp_code = generate_otp()
    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    await update_user_otp(db, user, otp_code, expires_at)
    background_tasks.add_task(send_otp_email, str(user.email), otp_code)

    return SuccessResponse(message="If that email is valid, a verification code has been sent.")


@router.post("/verify_otp")
async def verify_otp(
    body: VerifyOTPRequest,
    request: Request,
    response: Response,
    db: DB,
) -> SuccessResponse:
    """Verify OTP, mark account verified, issue tokens, and create a session."""
    user = await get_user_by_email(db, body.email)

    if user is None:
        hmac.compare_digest("dummy", body.otp_code)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code",
        )

    if user.is_verified:
        hmac.compare_digest("dummy", body.otp_code)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code",
        )

    if user.otp_code is None or user.otp_expires_at is None:
        hmac.compare_digest("dummy", body.otp_code)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code",
        )

    if (user.otp_attempts or 0) >= MAX_OTP_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Please request a new code.",
        )

    _check_otp_expiry(user.otp_expires_at)

    # C4: constant-time comparison to prevent timing side-channel attack
    if not hmac.compare_digest(str(user.otp_code), body.otp_code):
        new_attempts = await increment_otp_attempts(db, user)
        if new_attempts >= MAX_OTP_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Please request a new code.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code",
        )

    await mark_user_verified(db, user)
    await _create_token_pair_and_session(db, user, request, response)
    return SuccessResponse(message="Email verified successfully")


@router.post("/resend_otp")
@limiter.limit("3/10minutes")
async def resend_otp(
    request: Request,
    body: ResendOTPRequest,
    background_tasks: BackgroundTasks,
    db: DB,
) -> SuccessResponse:
    """Generate and send a new OTP code to an unverified email."""
    user = await get_user_by_email(db, body.email)

    if user is None or user.is_verified:
        return SuccessResponse(
            message="If an account with this email exists, a verification code was sent."
        )

    otp_code = generate_otp()
    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    await update_user_otp(db, user, otp_code, expires_at)
    background_tasks.add_task(send_otp_email, str(user.email), otp_code)

    return SuccessResponse(
        message="If an account with this email exists, a verification code was sent."
    )


# ---------------------------------------------------------------------------
# Login / Logout / Refresh
# ---------------------------------------------------------------------------


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: DB,
) -> SuccessResponse:
    """Authenticate a user, create a session, set auth cookies, and return success."""
    if not await verify_turnstile(body.cf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CAPTCHA verification failed",
        )

    user = await get_user_by_email(db, body.email)

    if user is None:
        verify_password(body.password, DUMMY_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Check account lockout
    if user.locked_until is not None:
        locked_until = _normalize_tz(user.locked_until)
        if locked_until > datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Account temporarily locked due to too many failed "
                "login attempts. Please try again later.",
            )
        await reset_failed_logins(db, user)

    if not verify_password(body.password, user.hashed_password):
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
    await _create_token_pair_and_session(db, user, request, response)
    return SuccessResponse(message="Login successful")


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    db: DB,
) -> SuccessResponse:
    """Rotate the refresh token and issue a new access token (one-time use per session)."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token"
        )

    try:
        payload = decode_refresh_token(refresh_token)
        email, jti = _validate_refresh_payload(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc

    user = await get_user_by_email(db, email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    session = await get_session_by_jti(db, jti)
    if session is None or session.user_id != user.id:
        # JTI mismatch — possible token theft → nuke all sessions for this user
        await delete_all_user_sessions(db, user.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Rotate: new JTI, same session row (preserves device info / created_at)
    new_refresh, new_jti = create_refresh_token({"sub": email})
    new_expires = _session_expires_at()
    await rotate_session_jti(db, session, new_jti, new_expires)

    new_access = create_access_token(
        {
            "sub": email,
            "ver": user.token_version or 0,
            "sid": session.id,
        }
    )
    set_auth_cookies(response, new_access, new_refresh)
    return SuccessResponse(message="Tokens refreshed")


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    db: DB,
) -> SuccessResponse:
    """Log out this device only — deletes the current session, clears cookies."""
    # Identify and delete only this session (other devices unaffected)
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = decode_refresh_token(refresh_token)
            jti = payload.get("jti")
            if jti:
                await delete_session_by_jti(db, jti)
        except jwt.InvalidTokenError as exc:
            logger.debug("logout_refresh_token_decode_failed", error=str(exc))

    clear_auth_cookies(response)
    logger.info("logout", user_id=current_user.id)
    return SuccessResponse(message="Logged out successfully")


# ---------------------------------------------------------------------------
# Current user / profile
# ---------------------------------------------------------------------------


@router.get("/me")
async def me(current_user: CurrentUser) -> UserResponse:
    """Return the currently authenticated user."""
    return UserResponse.model_validate(current_user)


@router.put("/profile")
async def update_profile(
    body: UpdateProfileRequest,
    current_user: CurrentUser,
    db: DB,
) -> UserResponse:
    """Update the current user's display name."""
    await update_user_name(db, current_user, body.first_name, body.last_name)
    logger.info("profile_updated", user_id=current_user.id)
    return UserResponse.model_validate(current_user)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    current_user: CurrentUser,
    db: DB,
) -> SuccessResponse:
    """Change password — revokes ALL sessions and access tokens, re-issues for current device."""
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    await update_user_password(db, current_user, hash_password(body.new_password))

    # Revoke everything — delete all sessions and bump token_version
    await delete_all_user_sessions(db, current_user.id)
    await bump_token_version(db, current_user)

    # Re-issue tokens for the current device only
    await _create_token_pair_and_session(db, current_user, request, response)

    logger.info("password_changed", user_id=current_user.id)
    return SuccessResponse(message="Password changed successfully")


# ---------------------------------------------------------------------------
# Session management (Google/Microsoft-style "Active sessions" settings page)
# ---------------------------------------------------------------------------


@router.get("/sessions")
async def list_sessions(
    current_user: CurrentUser,
    current_session_id: CurrentSessionId,
    db: DB,
) -> list[SessionResponse]:
    """List all active sessions for the current user, marking the calling session."""
    sessions = await get_active_sessions_for_user(db, current_user.id)
    return [
        SessionResponse(
            id=s.id,
            ip_address=s.ip_address,
            device_name=s.device_name,
            browser=s.browser,
            os=s.os,
            is_mobile=bool(s.is_mobile),
            created_at=s.created_at,
            last_used_at=s.last_used_at,
            is_current=(s.id == current_session_id),
        )
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
async def terminate_session(
    session_id: int,
    current_user: CurrentUser,
    db: DB,
) -> SuccessResponse:
    """Terminate a specific session (remote logout from another device)."""
    await delete_session_by_id(db, session_id, current_user.id)
    logger.info("session_terminated", user_id=current_user.id, session_id=session_id)
    return SuccessResponse(message="Session terminated")


@router.post("/sessions/logout-all")
async def logout_all_sessions(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    db: DB,
) -> SuccessResponse:
    """Revoke all sessions and access tokens, then re-login this device."""
    await delete_all_user_sessions(db, current_user.id)
    await bump_token_version(db, current_user)
    await _create_token_pair_and_session(db, current_user, request, response)
    logger.info("all_sessions_revoked", user_id=current_user.id)
    return SuccessResponse(message="All other sessions have been terminated")


# ---------------------------------------------------------------------------
# Account deletion
# ---------------------------------------------------------------------------


@router.post("/delete-account/request")
@limiter.limit("3/10minutes")
async def request_account_deletion(
    request: Request,
    body: DeleteAccountRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: DB,
) -> SuccessResponse:
    """Verify password and send an OTP to confirm account deletion."""
    if not verify_password(body.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect",
        )

    otp_code = generate_otp()
    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    await update_user_otp(db, current_user, otp_code, expires_at)
    background_tasks.add_task(send_account_deletion_otp_email, str(current_user.email), otp_code)
    return SuccessResponse(message="Confirmation code sent to your email")


@router.post("/delete-account/confirm")
@limiter.limit("5/10minutes")
async def confirm_account_deletion(
    request: Request,
    body: DeleteAccountConfirmRequest,
    response: Response,
    current_user: CurrentUser,
    db: DB,
) -> SuccessResponse:
    """Confirm account deletion by verifying the OTP code."""
    if current_user.otp_code is None or current_user.otp_expires_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active confirmation code. Please request account deletion first.",
        )

    if (current_user.otp_attempts or 0) >= MAX_OTP_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Please request a new code.",
        )

    if _normalize_tz(current_user.otp_expires_at) < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation code has expired. Please request a new one.",
        )

    # C4: constant-time comparison
    if not hmac.compare_digest(str(current_user.otp_code), body.otp_code):
        new_attempts = await increment_otp_attempts(db, current_user)
        if new_attempts >= MAX_OTP_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Please request a new code.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid confirmation code",
        )

    user_id = current_user.id
    await delete_user(db, current_user)  # cascade deletes sessions + documents
    clear_auth_cookies(response)
    logger.info("account_deleted", user_id=user_id)
    return SuccessResponse(message="Account deleted successfully")
