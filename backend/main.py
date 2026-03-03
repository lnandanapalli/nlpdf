"""NLPDF API application."""

import asyncio
import shutil
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

# Workaround for ConnectionResetError on Windows with ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from backend.config import settings
from backend.logging import setup_logging
from backend.rate_limit import limiter
from backend.routers.llm_router import router as llm_router
from backend.routers.auth_router import router as auth_router
from backend.security import UPLOAD_DIR

# Initialize structured logging before anything else
setup_logging()
logger = structlog.get_logger("nlpdf.main")


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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle."""
    _cleanup_old_uploads()
    yield


app = FastAPI(title="NLPDF API", version="0.2.0", lifespan=lifespan)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,  # type: ignore
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> Response:
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )


@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    import asyncio

    try:
        response = await asyncio.wait_for(
            call_next(request), timeout=settings.REQUEST_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        logger.warning("request_timeout", path=request.url.path)
        return JSONResponse(
            status_code=504,
            content={"detail": "Request timed out. Try a smaller file."},
        )
    return response


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    from backend.auth.csrf import verify_csrf_token

    error_response = verify_csrf_token(request)
    if error_response is not None:
        return error_response
    return await call_next(request)


app.include_router(llm_router)
app.include_router(auth_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "NLPDF API is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}
