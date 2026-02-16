"""Validators for rotation-related operations."""

from backend.validators.page_validators import validate_page_indices


def validate_rotation_angle(rotation: int) -> int:
    """
    Validate rotation angle.

    Args:
        rotation: Rotation angle in degrees

    Returns:
        Validated rotation angle

    Raises:
        ValueError: If rotation is not a valid multiple of 90
    """
    valid_rotations = {90, 180, 270, -90, -180, -270, 0, 360, -360}

    if rotation not in valid_rotations:
        raise ValueError(
            f"Invalid rotation angle {rotation}. "
            f"Must be a multiple of 90 degrees (90, 180, 270, -90, -180, -270)"
        )

    return rotation


def validate_rotation_specs(specs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """
    Validate rotation specifications by reusing existing validators.

    Args:
        specs: List of (page_num, angle) tuples (1-indexed, clockwise only)
               Example: [(1, 90), (3, 180), (5, 270)]

    Returns:
        Validated rotation specifications

    Raises:
        ValueError: If validation fails
    """
    if not specs:
        raise ValueError("At least one rotation specification must be provided")

    # Extract page numbers and validate using existing validator
    page_numbers = [page_num for page_num, _ in specs]
    validate_page_indices(page_numbers)

    # Validate each angle (clockwise only: 90, 180, 270)
    valid_angles = {90, 180, 270}
    for i, (_, angle) in enumerate(specs):
        if angle not in valid_angles:
            raise ValueError(
                f"Spec {i}: Invalid angle {angle}. Must be 90, 180, or 270 (clockwise)"
            )

    return specs
