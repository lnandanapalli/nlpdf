"""Tests for Pydantic schemas and LLM JSON validation."""

from pydantic import ValidationError
import pytest

from backend.schemas.compress_schema import CompressParams
from backend.schemas.llm_schema import (
    CompressOperation,
    MergeOperation,
    RotateOperation,
    SplitOperation,
    validate_llm_json,
)
from backend.schemas.rotate_schema import RotateParams
from backend.schemas.split_schema import SplitParams

# ── CompressParams ───────────────────────────────────────────────────────────


class TestCompressParams:
    """Tests for CompressParams schema."""

    @pytest.mark.parametrize("level", [1, 2, 3])
    def test_valid_levels(self, level: int):
        params = CompressParams(level=level)  # type: ignore[arg-type]
        assert params.level == level

    def test_level_0_rejected(self):
        with pytest.raises(ValidationError):
            CompressParams(level=0)  # type: ignore[arg-type]

    def test_level_4_rejected(self):
        with pytest.raises(ValidationError):
            CompressParams(level=4)  # type: ignore[arg-type]

    def test_string_rejected(self):
        with pytest.raises(ValidationError):
            CompressParams(level="high")  # type: ignore[arg-type]


# ── SplitParams ──────────────────────────────────────────────────────────────


class TestSplitParams:
    """Tests for SplitParams schema."""

    def test_valid_params(self):
        params = SplitParams(page_ranges=[(1, 5)], merge=True)
        assert params.page_ranges == [(1, 5)]
        assert params.merge is True

    def test_merge_defaults_true(self):
        params = SplitParams(page_ranges=[(1, 5)])
        assert params.merge is True

    def test_multiple_ranges(self):
        params = SplitParams(page_ranges=[(1, 5), (10, 15)], merge=False)
        assert len(params.page_ranges) == 2
        assert params.merge is False

    def test_bad_range_raises(self):
        with pytest.raises(ValidationError):
            SplitParams(page_ranges=[(5, 1)])


# ── RotateParams ─────────────────────────────────────────────────────────────


class TestRotateParams:
    """Tests for RotateParams schema."""

    def test_valid_rotations(self):
        params = RotateParams(rotations=[(1, 90), (3, 180)])
        assert params.rotations == [(1, 90), (3, 180)]

    def test_invalid_angle_raises(self):
        with pytest.raises(ValidationError):
            RotateParams(rotations=[(1, 45)])

    def test_empty_rotations_raises(self):
        with pytest.raises(ValidationError):
            RotateParams(rotations=[])


# ── validate_llm_json ────────────────────────────────────────────────────────


class TestValidateLlmJson:
    """Tests for validate_llm_json dispatch."""

    def test_compress_operation(self):
        result = validate_llm_json({"operation": "compress", "parameters": {"level": 2}})
        assert isinstance(result, CompressOperation)
        assert result.parameters.level == 2

    def test_split_operation(self):
        result = validate_llm_json(
            {
                "operation": "split",
                "parameters": {"page_ranges": [[1, 5]], "merge": True},
            }
        )
        assert isinstance(result, SplitOperation)

    def test_rotate_operation(self):
        result = validate_llm_json({"operation": "rotate", "parameters": {"rotations": [[1, 90]]}})
        assert isinstance(result, RotateOperation)

    def test_merge_operation(self):
        result = validate_llm_json({"operation": "merge", "parameters": {}})
        assert isinstance(result, MergeOperation)

    def test_unknown_operation_raises(self):
        with pytest.raises(ValueError, match="Unknown operation"):
            validate_llm_json({"operation": "delete", "parameters": {}})

    def test_missing_operation_raises(self):
        with pytest.raises(ValueError, match="Unknown operation"):
            validate_llm_json({"parameters": {}})

    def test_invalid_compress_params_raises(self):
        with pytest.raises(ValueError, match="Invalid parameters"):
            validate_llm_json({"operation": "compress", "parameters": {"level": 99}})
