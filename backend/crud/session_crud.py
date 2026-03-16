"""CRUD operations for user sessions."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.session import Session


@dataclass(frozen=True, slots=True)
class SessionCreate:
    """Value object carrying all fields needed to create a session row.

    Using a dataclass eliminates the PLR0913 (too-many-arguments) issue
    on ``create_session`` while keeping the call site explicit.
    """

    user_id: int
    jti: str
    expires_at: datetime
    ip_address: str | None
    device_name: str | None
    browser: str | None
    os: str | None
    is_mobile: int
    user_agent: str | None


async def create_session(db: AsyncSession, data: SessionCreate) -> Session:
    """Create and flush a new session row. Returns the Session with its generated id."""
    session = Session(
        user_id=data.user_id,
        jti=data.jti,
        expires_at=data.expires_at,
        ip_address=data.ip_address,
        device_name=data.device_name,
        browser=data.browser,
        os=data.os,
        is_mobile=data.is_mobile,
        user_agent=data.user_agent,
    )
    db.add(session)
    await db.flush()  # Needed to populate session.id before the transaction commits
    return session


async def get_session_by_jti(db: AsyncSession, jti: str) -> Session | None:
    """Fetch a session by its refresh token JTI."""
    result = await db.execute(select(Session).where(Session.jti == jti))
    return result.scalars().first()


async def get_active_sessions_for_user(db: AsyncSession, user_id: int) -> list[Session]:
    """Return all non-expired sessions for a user, newest-first."""
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id)
        .where(Session.expires_at > datetime.now(UTC))
        .order_by(Session.last_used_at.desc())
    )
    return list(result.scalars().all())


async def rotate_session_jti(
    db: AsyncSession,
    session: Session,
    new_jti: str,
    new_expires_at: datetime,
) -> None:
    """Update a session's JTI and timestamps on token rotation."""
    session.jti = new_jti
    session.last_used_at = datetime.now(UTC)
    session.expires_at = new_expires_at


async def delete_session_by_jti(db: AsyncSession, jti: str) -> None:
    """Delete a single session by its current JTI (single-device logout)."""
    await db.execute(delete(Session).where(Session.jti == jti))


async def delete_session_by_id(db: AsyncSession, session_id: int, user_id: int) -> None:
    """Delete a session by PK, scoped to the owning user."""
    await db.execute(
        delete(Session).where(
            Session.id == session_id,
            Session.user_id == user_id,
        )
    )


async def delete_all_user_sessions(db: AsyncSession, user_id: int) -> None:
    """Revoke all sessions for a user (password change / logout-all)."""
    await db.execute(delete(Session).where(Session.user_id == user_id))


async def delete_expired_sessions(db: AsyncSession) -> int:
    """Delete all expired sessions. Returns the count of deleted rows."""
    result = cast(
        "CursorResult",
        await db.execute(delete(Session).where(Session.expires_at <= datetime.now(UTC))),
    )
    return result.rowcount
