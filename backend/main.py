"""NLPDF API application."""

import asyncio
import contextlib
import shutil
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

# ProactorEventLoop raises ConnectionResetError on Windows; the selector loop
# does not. The policy API is removed in 3.16, where the default is used instead.
if sys.platform == "win32" and sys.version_info < (3, 16):  # pragma: no cover
    _selector_policy = asyncio.WindowsSelectorEventLoopPolicy()
    asyncio.set_event_loop_policy(_selector_policy)  # ty: ignore[deprecated]

import structlog
from fastapi import Depends, FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.csrf import verify_csrf_token
from backend.config import settings
from backend.database import get_db
from backend.logging import cleanup_old_log_files, get_log_dir, setup_logging
from backend.rate_limit import limiter
from backend.routers.auth_router import router as auth_router
from backend.routers.document_router import router as document_router
from backend.routers.llm_router import router as llm_router
from backend.crud.session_crud import delete_expired_sessions
from backend.database import AsyncSessionLocal
from backend.security import UPLOAD_DIR

# Initialize structured logging before anything else
setup_logging()
logger = structlog.get_logger("nlpdf.main")

# Dependency type alias
DB = Annotated[AsyncSession, Depends(get_db)]


def _cleanup_old_uploads(max_age_seconds: int = 3600) -> None:
    """Delete upload files and directories older than max_age_seconds."""
    if not UPLOAD_DIR.exists():
        return
    cutoff = time.time() - max_age_seconds
    removed = 0
    for entry in UPLOAD_DIR.iterdir():
        try:
            if entry.stat().st_mtime < cutoff:
                if entry.is_dir():
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    entry.unlink(missing_ok=True)
                removed += 1
        except OSError:
            continue
    if removed:
        logger.info("startup_cleanup", removed=removed)


async def _cleanup_expired_sessions() -> None:
    """Delete expired session rows from the database."""
    try:
        async with AsyncSessionLocal() as db:
            removed = await delete_expired_sessions(db)
            await db.commit()
            if removed:
                logger.info("expired_sessions_cleaned", removed=removed)
    except Exception:
        logger.exception("session_cleanup_error")


async def _periodic_cleanup(interval_seconds: int = 3600) -> None:
    """Background task to clean up old uploads and expired sessions periodically."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            _cleanup_old_uploads()
        except Exception:  # periodic background task — any failure must not crash the app
            logger.exception("periodic_cleanup_error")
        try:
            log_dir = get_log_dir(settings.APP_ENV)
            removed = cleanup_old_log_files(log_dir)
            if removed:
                logger.info("periodic_log_cleanup", removed=removed)
        except Exception:
            logger.exception("periodic_log_cleanup_error")
        await _cleanup_expired_sessions()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle."""
    _cleanup_old_uploads()
    try:
        log_dir = get_log_dir(settings.APP_ENV)
        removed = cleanup_old_log_files(log_dir)
        if removed:
            logger.info("startup_log_cleanup", removed=removed)
    except Exception:
        logger.exception("startup_log_cleanup_error")
    cleanup_task = asyncio.create_task(_periodic_cleanup())
    yield
    cleanup_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await cleanup_task


app = FastAPI(title="NLPDF API", version="0.2.0", lifespan=lifespan)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,  # type: ignore[arg-type]
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)


# Keys in a pydantic error dict that echo back what the client sent. `input` is
# the offending value -- for a missing field, the entire request body -- and
# `ctx` can carry it too. `type`, `loc` and `msg` are what a client acts on.
_ECHOED_ERROR_KEYS = frozenset({"input", "ctx"})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> Response:
    """Return a 422 without echoing the values that failed validation.

    FastAPI's default handler serialises exc.errors() verbatim, so a missing
    field on /auth/login returns the whole submitted body -- including the
    plaintext password -- to the client, and onward to any proxy, CDN or
    browser error reporter that records response bodies.
    """
    detail = [
        {key: value for key, value in error.items() if key not in _ECHOED_ERROR_KEYS}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(detail)},
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> Response:
    """Return a 429 JSON response when the rate limit is exceeded."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )


@app.middleware("http")
async def timeout_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Abort requests that exceed REQUEST_TIMEOUT_SECONDS with a 504."""
    try:
        response = await asyncio.wait_for(
            call_next(request), timeout=settings.REQUEST_TIMEOUT_SECONDS
        )
    except TimeoutError:
        logger.warning("request_timeout", path=request.url.path)
        return JSONResponse(
            status_code=504,
            content={"detail": "Request timed out. Try a smaller file."},
        )
    return response


@app.middleware("http")
async def csrf_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Validate the CSRF double-submit token on state-mutating requests."""
    error_response = verify_csrf_token(request)
    if error_response is not None:
        return error_response
    return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Attach security headers (CSP, HSTS, etc.) to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "connect-src 'self'"
    )
    if settings.APP_ENV != "development":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
    return response


app.include_router(llm_router)
app.include_router(auth_router)
app.include_router(document_router)


@app.get("/")
def root() -> dict[str, str]:
    """Return a simple liveness message."""
    return {"message": "NLPDF API is running"}


@app.get("/health")
async def health(db: DB) -> dict[str, str]:
    """Execute a lightweight DB query to confirm the application is healthy."""
    await db.execute(text("SELECT 1"))
    return {"status": "healthy"}
