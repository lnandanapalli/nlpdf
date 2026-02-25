"""NLPDF API application."""

import asyncio
import sys

# Workaround for ConnectionResetError on Windows with ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from backend.config import settings
from backend.logging import setup_logging
from backend.routers.llm_router import router as llm_router
from backend.routers.auth_router import router as auth_router
from backend.security import get_client_ip

# Initialize structured logging before anything else
setup_logging()
logger = structlog.get_logger("nlpdf.main")

limiter = Limiter(key_func=get_client_ip, default_limits=["60/minute"])

app = FastAPI(title="NLPDF API", version="0.2.0")
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,  # type: ignore
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
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


app.include_router(llm_router)
app.include_router(auth_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "NLPDF API is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}
