"""Tests for rotation validators."""

import pytest

from backend.validators.rotation_validators import validate_rotation_specs


class TestValidateRotationSpecs:
    """Tests for validate_rotation_specs."""

    def test_valid_90_degrees(self):
        result = validate_rotation_specs([(1, 90)])
        assert result == [(1, 90)]

    def test_valid_180_degrees(self):
        result = validate_rotation_specs([(2, 180)])
        assert result == [(2, 180)]

    def test_valid_270_degrees(self):
        result = validate_rotation_specs([(3, 270)])
        assert result == [(3, 270)]

    def test_valid_multiple_specs(self):
        specs = [(1, 90), (3, 180), (5, 270)]
        result = validate_rotation_specs(specs)
        assert result == specs

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="At least one rotation"):
            validate_rotation_specs([])

    def test_invalid_angle_0_raises(self):
        with pytest.raises(ValueError, match="Invalid angle 0"):
            validate_rotation_specs([(1, 0)])

    def test_invalid_angle_45_raises(self):
        with pytest.raises(ValueError, match="Invalid angle 45"):
            validate_rotation_specs([(1, 45)])

    def test_invalid_angle_360_raises(self):
        with pytest.raises(ValueError, match="Invalid angle 360"):
            validate_rotation_specs([(1, 360)])

    def test_invalid_page_number_raises(self):
        with pytest.raises(ValueError, match="must be >= 1"):
            validate_rotation_specs([(0, 90)])

    def test_duplicate_page_numbers_raises(self):
        with pytest.raises(ValueError, match="Duplicate"):
            validate_rotation_specs([(1, 90), (1, 180)])
