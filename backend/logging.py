"""Centralized logging configuration using structlog."""

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import sys
import time

import structlog

from backend.config import settings

# Logging configuration constants
LOG_RETENTION_DAYS = 30
DEV_LOG_DIR = "./logs"


def get_log_dir(app_env: str, configured: str | None = None) -> Path | None:
    """Where to write log files, or None to log to stdout only.

    An explicit LOG_DIR always wins. Otherwise development writes to ./logs
    and production logs to stdout only. On Azure App Service the platform
    captures container stdout (Log stream, App Service logs, Log Analytics),
    while the container's own disk is wiped on every restart, and /home is
    persistent -- and shared by every instance -- only when App Service
    storage is enabled.
    """
    if configured:
        return Path(configured)
    if app_env == "production":
        return None
    return Path(DEV_LOG_DIR)


def cleanup_old_log_files(log_dir: Path | None, max_age_days: int = LOG_RETENTION_DAYS) -> int:
    """Deletes daily-rotated log files older than max_age_days.

    Only deletes files starting with 'app.log.' to avoid unlinking
    the active log file or other unrelated files.
    """
    if log_dir is None or not log_dir.exists() or not log_dir.is_dir():
        return 0

    cutoff_time = time.time() - (max_age_days * 86400)
    removed_count = 0

    for entry in log_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.name.startswith("app.log."):
            try:
                mtime = entry.stat().st_mtime
                if mtime < cutoff_time:
                    entry.unlink(missing_ok=True)
                    removed_count += 1
            except OSError:
                continue

    return removed_count


def setup_logging(log_level: int = logging.INFO) -> None:
    """Configure structlog and standard logging."""
    # Configure console (stdout) logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    log_dir = get_log_dir(settings.APP_ENV, settings.LOG_DIR)
    if log_dir is not None:
        _add_file_handler(log_dir, log_level)

    _configure_structlog()


def _add_file_handler(log_dir: Path, log_level: int) -> None:
    """Also write daily-rotated log files, falling back to stdout only on failure."""
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            filename=str(log_dir / "app.log"),
            when="midnight",
            interval=1,
            backupCount=LOG_RETENTION_DAYS,
            encoding="utf-8",
            utc=True,
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        file_handler.suffix = "%Y-%m-%d"
        logging.getLogger().addHandler(file_handler)
    except Exception as e:
        sys.stderr.write(
            f"WARNING: Could not configure file logging in {log_dir}: {e}. "
            "Falling back to console-only logging.\n"
        )


def _configure_structlog() -> None:
    """Configure structlog processors and factory (JSON lines)."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
