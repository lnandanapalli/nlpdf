"""Centralized logging configuration using structlog."""

import logging
import sys

import structlog


def setup_logging(log_level: int = logging.INFO) -> None:
    """
    Configure structlog and standard logging.

    This replaces the standard library logging formatters with structlog's
    JSON formatter for production (or a clear console renderer for local dev).
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

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
