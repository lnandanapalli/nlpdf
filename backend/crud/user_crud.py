"""CRUD operations for the User model."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.user import OTPPurpose, User

MAX_OTP_ATTEMPTS: int = 5
MAX_FAILED_LOGIN_ATTEMPTS: int = 5


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Fetch a user by email address."""
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalars().first()


async def create_user(
    db: AsyncSession,
    email: str,
    hashed_password: str,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    """Create a new user and flush to get the generated id."""
    user = User(
        email=email.lower(),
        hashed_password=hashed_password,
        first_name=first_name,
        last_name=last_name,
    )
    db.add(user)
    await db.flush()  # Needed to populate user.id before the transaction commits
    return user


async def update_user_otp(
    db: AsyncSession,
    user: User,
    otp_code: str,
    expires_at: datetime,
    purpose: OTPPurpose = OTPPurpose.SIGNUP,
) -> None:
    """Update the OTP code and expiration for a user, resetting attempt counter."""
    user.otp_code = otp_code
    user.otp_expires_at = expires_at
    user.otp_purpose = purpose
    user.otp_attempts = 0


async def increment_otp_attempts(db: AsyncSession, user: User) -> int:
    """Atomically increment OTP attempt counter and return the new count.

    Uses SQL UPDATE otp_attempts = otp_attempts + 1 RETURNING otp_attempts
    instead of a Python read-modify-write, preventing the TOCTOU race where
    two parallel requests both read the same stale count and both slip through
    the lockout gate.

    Also clears the OTP code in memory once the limit is reached so the
    caller can raise the appropriate error without a second DB round-trip.
    """
    result = await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(otp_attempts=User.otp_attempts + 1)
        .returning(User.otp_attempts)
    )
    new_count: int = result.scalar_one()
    user.otp_attempts = new_count  # keep in-memory object consistent
    if new_count >= MAX_OTP_ATTEMPTS:
        user.otp_code = None
        user.otp_expires_at = None
        user.otp_purpose = None
    return new_count


async def mark_user_verified(db: AsyncSession, user: User) -> None:
    """Mark a user as verified and clear the OTP fields."""
    user.is_verified = True
    user.otp_code = None
    user.otp_expires_at = None
    user.otp_purpose = None
    user.otp_attempts = 0


async def record_failed_login(db: AsyncSession, user: User) -> None:
    """Atomically increment failed login counter and lock after 5 failures.

    Uses SQL UPDATE failed_login_attempts = failed_login_attempts + 1 RETURNING
    instead of a Python read-modify-write, preventing the TOCTOU race where
    two parallel requests both read the same stale count and both slip through
    the lockout gate.
    """
    result = await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(failed_login_attempts=User.failed_login_attempts + 1)
        .returning(User.failed_login_attempts)
    )
    new_count: int = result.scalar_one()
    user.failed_login_attempts = new_count  # keep in-memory object consistent
    if new_count >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = datetime.now(UTC) + timedelta(minutes=15)


async def reset_failed_logins(db: AsyncSession, user: User) -> None:
    """Reset failed login counter and unlock on successful login."""
    user.failed_login_attempts = 0
    user.locked_until = None


async def update_user_name(db: AsyncSession, user: User, first_name: str, last_name: str) -> None:
    """Update the user's first and last name."""
    user.first_name = first_name
    user.last_name = last_name


async def update_user_password(db: AsyncSession, user: User, hashed_password: str) -> None:
    """Update the user's hashed password."""
    user.hashed_password = hashed_password


async def bump_token_version(db: AsyncSession, user: User) -> None:
    """Increment token_version to immediately invalidate all outstanding access tokens.

    Called on password change and logout-all. Because get_current_user already
    fetches the user row and checks payload['ver'] == user.token_version, bumping
    this value costs zero extra DB queries per request.
    """
    user.token_version = (user.token_version or 0) + 1


async def delete_user(db: AsyncSession, user: User) -> None:
    """Delete a user and all associated data (cascade handles documents and sessions)."""
    await db.delete(user)
