"""Tests for email PII masking."""

import pytest

from backend.utils.email_utils import mask_email


class TestMaskEmail:
    """mask_email is what keeps addresses out of the logs, so its edges matter."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("alice@example.com", "al****@example.com"),
            ("bob.smith@corp.co.uk", "bo****@corp.co.uk"),
            ("x@y.com", "x****@y.com"),
            ("ab@y.com", "ab****@y.com"),
        ],
    )
    def test_masks_local_part(self, raw, expected):
        assert mask_email(raw) == expected

    def test_domain_is_preserved(self):
        """The domain is kept deliberately: it is useful and not personal."""
        assert mask_email("someone@example.com").endswith("@example.com")

    def test_full_local_part_never_survives(self):
        local_part = "verylongusername"
        assert local_part not in mask_email(f"{local_part}@example.com")

    @pytest.mark.parametrize("raw", ["not-an-email", "", "no-at-sign.com"])
    def test_rejects_input_without_an_at_sign(self, raw):
        assert mask_email(raw) == "invalid-email"

    def test_splits_on_the_first_at_only(self):
        """A local part containing '@' must not spill into the output."""
        assert mask_email("we@ird@example.com") == "we****@ird@example.com"
