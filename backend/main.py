"""NLPDF API application."""

import asyncio
import logging

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from backend.routers import compress_router, merge_router, rotate_router, split_router
from backend.security import get_client_ip

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# --- Rate limiter ---
limiter = Limiter(key_func=get_client_ip, default_limits=["60/minute"])

app = FastAPI(title="NLPDF API", version="0.1.0")
app.state.limiter = limiter

# --- CORS ---
app.add_middleware(
    CORSMiddleware,  # type: ignore
    allow_origins=["*"],  # TODO: restrict to your frontend domain in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    max_age=600,
)


# --- Rate limit error handler ---
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )


# --- Request timeout middleware ---
REQUEST_TIMEOUT_SECONDS = 120


@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    try:
        response = await asyncio.wait_for(
            call_next(request), timeout=REQUEST_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={"detail": "Request timed out. Try a smaller file."},
        )
    return response


# Include routers
app.include_router(compress_router)
app.include_router(split_router)
app.include_router(merge_router)
app.include_router(rotate_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "NLPDF API is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}
