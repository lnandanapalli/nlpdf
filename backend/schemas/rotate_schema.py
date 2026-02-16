"""Schemas for PDF rotation."""

from pydantic import BaseModel, Field, field_validator

from backend.validators import validate_rotation_specs


class RotateParams(BaseModel):
    """Validated parameters for PDF rotation."""

    rotations: list[tuple[int, int]] = Field(
        ...,
        description="List of [page_num, angle] tuples (1-indexed, clockwise only). "
        "Example: [[1, 90], [3, 180], [5, 270]] rotates pages with specified angles",
    )

    @field_validator("rotations")
    @classmethod
    def check_rotations(cls, v: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Validate rotation specifications using reusable validator."""
        return validate_rotation_specs(v)
