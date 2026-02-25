"""Tests for page validators."""

import pytest

from backend.validators.page_validators import (
    validate_page_indices,
    validate_page_ranges,
)

# ── validate_page_ranges ─────────────────────────────────────────────────────


class TestValidatePageRanges:
    """Tests for validate_page_ranges."""

    def test_valid_single_range(self):
        result = validate_page_ranges([(1, 5)])
        assert result == [(1, 5)]

    def test_valid_multiple_ranges(self):
        result = validate_page_ranges([(1, 5), (10, 15)])
        assert result == [(1, 5), (10, 15)]

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="At least one page range"):
            validate_page_ranges([])

    def test_too_many_ranges_raises(self):
        ranges = [(i, i) for i in range(1, 102)]
        with pytest.raises(ValueError, match="Maximum 100 page ranges"):
            validate_page_ranges(ranges)

    def test_start_less_than_one_raises(self):
        with pytest.raises(ValueError, match="must be >= 1"):
            validate_page_ranges([(0, 5)])

    def test_end_less_than_one_raises(self):
        with pytest.raises(ValueError, match="must be >= 1"):
            validate_page_ranges([(-1, 5)])

    def test_start_greater_than_end_raises(self):
        with pytest.raises(ValueError, match="must be <= end"):
            validate_page_ranges([(10, 5)])

    def test_range_exceeds_10000_raises(self):
        with pytest.raises(ValueError, match="Maximum 10000 pages per range"):
            validate_page_ranges([(1, 10002)])

    def test_page_number_exceeds_50000_raises(self):
        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            validate_page_ranges([(50001, 50002)])

    def test_overlapping_ranges_raises(self):
        with pytest.raises(ValueError, match="Overlapping ranges"):
            validate_page_ranges([(1, 10), (5, 15)])

    def test_adjacent_ranges_not_overlapping(self):
        """Ranges [1,5] and [6,10] do not overlap."""
        result = validate_page_ranges([(1, 5), (6, 10)])
        assert result == [(1, 5), (6, 10)]

    def test_exactly_100_ranges(self):
        """Boundary: exactly 100 ranges should be valid."""
        ranges = [(i * 2, i * 2) for i in range(1, 101)]
        result = validate_page_ranges(ranges)
        assert len(result) == 100


# ── validate_page_indices ────────────────────────────────────────────────────


class TestValidatePageIndices:
    """Tests for validate_page_indices."""

    def test_none_returns_none(self):
        assert validate_page_indices(None) is None

    def test_valid_indices(self):
        result = validate_page_indices([1, 3, 5])
        assert result == [1, 3, 5]

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="at least one index"):
            validate_page_indices([])

    def test_too_many_indices_raises(self):
        indices = list(range(1, 10002))
        with pytest.raises(ValueError, match="Maximum 10000"):
            validate_page_indices(indices)

    def test_duplicate_indices_raises(self):
        with pytest.raises(ValueError, match="Duplicate"):
            validate_page_indices([1, 2, 1])

    def test_index_less_than_one_raises(self):
        with pytest.raises(ValueError, match="must be >= 1"):
            validate_page_indices([0])

    def test_index_exceeds_50000_raises(self):
        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            validate_page_indices([50001])

    def test_index_exceeds_max_pages_raises(self):
        with pytest.raises(ValueError, match="exceeds PDF page count"):
            validate_page_indices([11], max_pages=10)

    def test_index_within_max_pages(self):
        result = validate_page_indices([1, 5, 10], max_pages=10)
        assert result == [1, 5, 10]
