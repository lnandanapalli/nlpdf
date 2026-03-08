"""Database connection and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings

_trust_cert = "yes" if settings.APP_ENV == "development" else "no"

database_url = URL.create(
    drivername="mssql+aioodbc",
    username=settings.DB_USER,
    password=settings.DB_PASSWORD,
    host=settings.DB_HOST,
    port=settings.DB_PORT,
    database=settings.DB_NAME,
    query={
        "driver": settings.DB_DRIVER,
        "Encrypt": "yes",
        "TrustServerCertificate": _trust_cert,
        "Connection Timeout": "30",
    },
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


from sqlalchemy.orm import declarative_base  # noqa: E402

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
