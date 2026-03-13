"""Alembic migration environment (synchronous, for SQL Server via pyodbc)."""

from logging.config import fileConfig

from sqlalchemy import URL, create_engine, pool

from alembic import context

from backend.config import settings
from backend.database import Base

# Import all models so metadata is populated
import backend.models  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

_trust_cert = "yes" if settings.APP_ENV == "development" else "no"

# Build the sync URL. Prioritize the override (converting to sync if needed),
# then fall back to the MSSQL constructor.
if settings.DATABASE_URL_OVERRIDE:
    _sync_url = str(settings.DATABASE_URL_OVERRIDE).replace("+aioodbc", "+pyodbc").replace("+aiosqlite", "")
else:
    _sync_url = str(URL.create(
        drivername="mssql+pyodbc",
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
    ))

# ConfigParser (used by Alembic) interprets '%' as interpolation. Must escape it.
config.set_main_option("sqlalchemy.url", _sync_url.replace("%", "%%"))

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout, no connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a synchronous engine."""
    connectable = create_engine(
        _sync_url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
