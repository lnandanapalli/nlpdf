"""Database connection and session management."""

from collections.abc import AsyncGenerator

from fastapi import HTTPException, status
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import structlog

from backend.base import Base
from backend.config import settings

logger = structlog.get_logger(__name__)

if settings.DATABASE_URL_OVERRIDE:
    database_url: str | URL = settings.DATABASE_URL_OVERRIDE
else:
    _trust_cert = "yes" if settings.APP_ENV == "development" else "no"
    _query = {
        "driver": settings.DB_DRIVER,
        "TrustServerCertificate": _trust_cert,
        "Connection Timeout": "30",
    }
    # ODBC 18 requires Encrypt=yes by default, but ODBC 17 can be picky
    if "18" in settings.DB_DRIVER:
        _query["Encrypt"] = "yes"

    database_url = URL.create(
        drivername="mssql+aioodbc",
        username=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        query=_query,
    )

engine = create_async_engine(
    database_url,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


__all__ = ["AsyncSessionLocal", "Base", "engine", "get_db", "is_server_fault"]

# Exceptions that mean the caller got it wrong, not that the server broke.
# Their reprs embed the request body, which on the auth routes contains the
# submitted password, so they must never be logged with a traceback.
CLIENT_FAULTS: tuple[type[Exception], ...] = (
    RequestValidationError,
    RateLimitExceeded,
)


def is_server_fault(exc: Exception) -> bool:
    """Whether an exception raised while handling a request is the server's fault.

    The default is deliberately True: an exception nobody has classified is
    treated as a server fault and logged, so a new or unexpected type is noisy
    rather than silent. Only positively identified client faults are excluded.
    """
    if isinstance(exc, CLIENT_FAULTS):
        return False
    if isinstance(exc, HTTPException):
        return exc.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR
    return True


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            if is_server_fault(exc):
                extra = {"status_code": exc.status_code} if isinstance(exc, HTTPException) else {}
                logger.exception("db_session_error", **extra)
            raise
