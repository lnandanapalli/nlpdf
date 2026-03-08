"""CRUD operations for the User model."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.user import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Fetch a user by email address."""
    result = await db.execute(select(User).where(User.email == email))
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
        email=email,
        hashed_password=hashed_password,
        first_name=first_name,
        last_name=last_name,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user_otp(
    db: AsyncSession, user: User, otp_code: str, expires_at: datetime
) -> None:
    """Update the OTP code and expiration for a user, resetting attempt counter."""
    user.otp_code = otp_code
    user.otp_expires_at = expires_at
    user.otp_attempts = 0
    await db.commit()
    await db.refresh(user)


async def increment_otp_attempts(db: AsyncSession, user: User) -> None:
    """Increment the OTP attempt counter. Invalidate OTP after 5 failures."""
    user.otp_attempts = (user.otp_attempts or 0) + 1
    if user.otp_attempts >= 5:
        user.otp_code = None
        user.otp_expires_at = None
    await db.commit()
    await db.refresh(user)


async def mark_user_verified(db: AsyncSession, user: User) -> None:
    """Mark a user as verified and clear the OTP fields."""
    user.is_verified = True
    user.otp_code = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    await db.commit()
    await db.refresh(user)


async def record_failed_login(db: AsyncSession, user: User) -> None:
    """Increment failed login counter and lock after 5 failures."""
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= 5:
        from datetime import timedelta, timezone

        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    await db.commit()
    await db.refresh(user)


async def reset_failed_logins(db: AsyncSession, user: User) -> None:
    """Reset failed login counter and unlock on successful login."""
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()
    await db.refresh(user)


async def update_refresh_token_jti(db: AsyncSession, user: User, jti: str) -> None:
    """Store the JTI of the user's current valid refresh token."""
    user.refresh_token_jti = jti
    await db.commit()
    await db.refresh(user)


async def clear_refresh_token_jti(db: AsyncSession, user: User) -> None:
    """Revoke the user's refresh token by clearing the stored JTI."""
    user.refresh_token_jti = None
    await db.commit()
    await db.refresh(user)


async def update_user_name(
    db: AsyncSession, user: User, first_name: str, last_name: str
) -> None:
    """Update the user's first and last name."""
    user.first_name = first_name
    user.last_name = last_name
    await db.commit()
    await db.refresh(user)


async def update_user_password(
    db: AsyncSession, user: User, hashed_password: str
) -> None:
    """Update the user's hashed password."""
    user.hashed_password = hashed_password
    await db.commit()
    await db.refresh(user)


async def delete_user(db: AsyncSession, user: User) -> None:
    """Delete a user and all associated data (cascade handles documents)."""
    await db.delete(user)
    await db.commit()
