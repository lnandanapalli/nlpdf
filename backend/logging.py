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
PROD_LOG_DIR = "/home/nlpdf_logs"
DEV_LOG_DIR = "./logs"


def get_log_dir(app_env: str) -> Path:
    """Determine the appropriate log directory based on APP_ENV."""
    if app_env == "production":
        return Path(PROD_LOG_DIR)
    return Path(DEV_LOG_DIR)


def cleanup_old_log_files(log_dir: Path, max_age_days: int = LOG_RETENTION_DAYS) -> int:
    """Deletes daily-rotated log files older than max_age_days.

    Only deletes files starting with 'app.log.' to avoid unlinking
    the active log file or other unrelated files.
    """
    if not log_dir.exists() or not log_dir.is_dir():
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

    # Configure daily rotating file handler for persistent logs
    log_dir = get_log_dir(settings.APP_ENV)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"

        file_handler = TimedRotatingFileHandler(
            filename=str(log_file),
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

    # Configure structlog processors and factory
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
