"""CRUD operations for the User model."""

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
