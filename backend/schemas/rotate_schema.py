"""Schemas for PDF rotation."""

from pydantic import BaseModel, Field


class RotateParams(BaseModel):
    """Validated parameters for PDF rotation."""

    rotation: int = Field(..., description="Rotation angle (90, 180, 270, or negative)")
    page_indices: list[int] | None = Field(
        None, description="Page indices to rotate (0-indexed), None for all pages"
    )
