"""API routers."""

from backend.routers.compress_router import router as compress_router
from backend.routers.merge_router import router as merge_router
from backend.routers.rotate_router import router as rotate_router
from backend.routers.split_router import router as split_router

__all__ = [
    "compress_router",
    "split_router",
    "merge_router",
    "rotate_router",
]
