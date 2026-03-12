"""Tests for the rotate service."""

from pypdf import PdfReader
import pytest

from backend.services.rotate_service import rotate_pdf


class TestRotatePdf:
    """Tests for rotate_pdf."""

    def test_rotate_single_page_90(self, sample_pdf, tmp_output):
        result = rotate_pdf(sample_pdf, [(1, 90)], tmp_output)

        assert result == tmp_output
        assert tmp_output.exists()
        reader = PdfReader(tmp_output)
        assert len(reader.pages) == 5

    def test_rotate_single_page_180(self, sample_pdf, tmp_output):
        rotate_pdf(sample_pdf, [(2, 180)], tmp_output)

        reader = PdfReader(tmp_output)
        assert len(reader.pages) == 5

    def test_rotate_single_page_270(self, sample_pdf, tmp_output):
        rotate_pdf(sample_pdf, [(3, 270)], tmp_output)

        reader = PdfReader(tmp_output)
        assert len(reader.pages) == 5

    def test_rotate_multiple_pages(self, sample_pdf, tmp_output):
        rotate_pdf(sample_pdf, [(1, 90), (3, 180), (5, 270)], tmp_output)

        reader = PdfReader(tmp_output)
        assert len(reader.pages) == 5

    def test_output_has_all_pages_including_unrotated(self, sample_pdf, tmp_output):
        """Pages not in the rotation list should still be present."""
        rotate_pdf(sample_pdf, [(1, 90)], tmp_output)

        reader = PdfReader(tmp_output)
        assert len(reader.pages) == 5

    def test_page_exceeds_count_raises(self, sample_pdf, tmp_output):
        with pytest.raises(ValueError, match="exceeds PDF page count"):
            rotate_pdf(sample_pdf, [(99, 90)], tmp_output)

    def test_rotation_metadata_applied(self, sample_pdf, tmp_output):
        """Rotating 90° should set /Rotate on the page."""
        rotate_pdf(sample_pdf, [(1, 90)], tmp_output)

        rotated = PdfReader(tmp_output)
        page = rotated.pages[0]
        # pypdf stores rotation as page metadata; the effective rotation
        # is the value of /Rotate (mod 360)
        assert page.get("/Rotate") in (90, -270)
