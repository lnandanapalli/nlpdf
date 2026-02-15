"""Schemas for PDF rotation."""

from pydantic import BaseModel, Field, field_validator

from backend.validators import validate_page_indices, validate_rotation_angle


class RotateParams(BaseModel):
    """Validated parameters for PDF rotation."""

    rotation: int = Field(..., description="Rotation angle (90, 180, 270, or negative)")
    page_indices: list[int] | None = Field(
        None,
        description="Page indices to rotate (1-indexed). "
        "Example: [1, 3, 5] rotates pages 1, 3, and 5. None = all pages",
    )

    @field_validator("rotation")
    @classmethod
    def check_rotation(cls, v: int) -> int:
        """Validate rotation angle using reusable validator."""
        return validate_rotation_angle(v)

    @field_validator("page_indices")
    @classmethod
    def check_page_indices(cls, v: list[int] | None) -> list[int] | None:
        """Validate page indices using reusable validator."""
        return validate_page_indices(v)
