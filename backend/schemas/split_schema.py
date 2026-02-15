"""Schemas for PDF splitting."""

from pydantic import BaseModel, Field


class SplitParams(BaseModel):
    """Validated parameters for PDF splitting."""

    page_ranges: list[tuple[int, int]] = Field(
        ..., description="List of (start, end) page ranges (0-indexed, end exclusive)"
    )
