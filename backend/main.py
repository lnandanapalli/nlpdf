"""NLPDF API application."""

import asyncio
import contextlib
import shutil
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

# Workaround for ConnectionResetError on Windows with ProactorEventLoop
if sys.platform == "win32":  # pragma: no cover
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import structlog
from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.csrf import verify_csrf_token
from backend.config import settings
from backend.database import get_db
from backend.logging import setup_logging
from backend.rate_limit import limiter
from backend.routers.auth_router import router as auth_router
from backend.routers.llm_router import router as llm_router
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


async def _periodic_cleanup(interval_seconds: int = 3600) -> None:
    """Background task to clean up old uploads periodically."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            _cleanup_old_uploads()
        except Exception:  # periodic background task — any failure must not crash the app
            logger.exception("periodic_cleanup_error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle."""
    _cleanup_old_uploads()
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
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(llm_router)
app.include_router(auth_router)


@app.get("/")
def root() -> dict[str, str]:
    """Return a simple liveness message."""
    return {"message": "NLPDF API is running"}


@app.get("/health")
async def health(db: DB) -> dict[str, str]:
    """Execute a lightweight DB query to confirm the application is healthy."""
    await db.execute(text("SELECT 1"))
    return {"status": "healthy"}
