"""CRUD operations for the User model."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.user import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Fetch a user by email address."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()


async def create_user(db: AsyncSession, email: str, hashed_password: str) -> User:
    """Create a new user and flush to get the generated id."""
    user = User(email=email, hashed_password=hashed_password)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user_otp(
    db: AsyncSession, user: User, otp_code: str, expires_at: datetime
) -> None:
    """Update the OTP code and expiration for a user."""
    user.otp_code = otp_code
    user.otp_expires_at = expires_at
    await db.commit()
    await db.refresh(user)


async def mark_user_verified(db: AsyncSession, user: User) -> None:
    """Mark a user as verified and clear the OTP fields."""
    user.is_verified = True
    user.otp_code = None
    user.otp_expires_at = None
    await db.commit()
    await db.refresh(user)
