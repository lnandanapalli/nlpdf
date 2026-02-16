"""Validators for page-related operations."""


def validate_page_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """
    Validate page ranges for security and correctness.

    Args:
        ranges: List of (start, end) tuples (1-indexed, inclusive)
                Example: [1, 5] means pages 1, 2, 3, 4, 5

    Returns:
        Validated page ranges

    Raises:
        ValueError: If validation fails
    """
    if not ranges:
        raise ValueError("At least one page range must be provided")

    if len(ranges) > 100:
        raise ValueError("Maximum 100 page ranges allowed")

    for i, (start, end) in enumerate(ranges):
        # Check for values less than 1 (1-indexed)
        if start < 1 or end < 1:
            raise ValueError(
                f"Range {i}: Page numbers must be >= 1 "
                f"(got start={start}, end={end})"
            )

        # Check start <= end (inclusive ranges)
        if start > end:
            raise ValueError(
                f"Range {i}: Start page ({start}) must be <= end page ({end})"
            )

        # Check for excessively large ranges (prevent DoS)
        if end - start + 1 > 10000:
            raise ValueError(
                f"Range {i}: Maximum 10000 pages per range allowed "
                f"(got {end - start + 1})"
            )

        # Check for unreasonably large page numbers (prevent DoS)
        if end > 50000:
            raise ValueError(
                f"Range {i}: Page number {end} exceeds maximum allowed (50000)"
            )

    # Check for overlapping ranges
    sorted_ranges = sorted(ranges, key=lambda x: x[0])
    for i in range(len(sorted_ranges) - 1):
        curr_start, curr_end = sorted_ranges[i]
        next_start, next_end = sorted_ranges[i + 1]

        if curr_end >= next_start:
            raise ValueError(
                f"Overlapping ranges detected: [{curr_start}, {curr_end}] "
                f"overlaps with [{next_start}, {next_end}]"
            )

    return ranges


def validate_page_indices(
    indices: list[int] | None, max_pages: int | None = None
) -> list[int] | None:
    """
    Validate page indices.

    Args:
        indices: List of page indices (1-indexed), or None for all pages
                 Example: [1, 3, 5] means pages 1, 3, and 5
        max_pages: Maximum number of pages in the PDF (if known)

    Returns:
        Validated page indices

    Raises:
        ValueError: If validation fails
    """
    if indices is None:
        return None

    if not indices:
        raise ValueError(
            "If page_indices is provided, it must contain at least one index"
        )

    if len(indices) > 10000:
        raise ValueError("Maximum 10000 page indices allowed")

    # Check for duplicates
    if len(indices) != len(set(indices)):
        raise ValueError("Duplicate page indices are not allowed")

    for idx in indices:
        if idx < 1:
            raise ValueError(f"Page index {idx} must be >= 1 (1-indexed)")

        if idx > 50000:
            raise ValueError(f"Page index {idx} exceeds maximum allowed (50000)")

        if max_pages is not None and idx > max_pages:
            raise ValueError(f"Page index {idx} exceeds PDF page count ({max_pages})")

    return indices
