"""Schemas for PDF compression."""

from typing import Literal

from pydantic import BaseModel, Field


class CompressParams(BaseModel):
    """Validated parameters for PDF compression."""

    level: Literal[1, 2, 3] = Field(
        ...,
        description="Compression level: 1 (low, 40% downscale), "
        "2 (medium, 60% downscale), 3 (high, 80% downscale)",
    )
