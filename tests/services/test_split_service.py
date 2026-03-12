"""Tests for the split service."""

import zipfile

from pypdf import PdfReader
import pytest

from backend.services.split_service import split_pdf


class TestSplitPdfMerge:
    """Tests for split_pdf with merge=True."""

    def test_extract_first_two_pages(self, sample_pdf, tmp_output):
        result = split_pdf(sample_pdf, [(1, 2)], merge=True, output_path=tmp_output)

        assert result == tmp_output
        assert tmp_output.exists()
        reader = PdfReader(tmp_output)
        assert len(reader.pages) == 2

    def test_extract_multiple_ranges(self, sample_pdf, tmp_output):
        split_pdf(sample_pdf, [(1, 2), (4, 5)], merge=True, output_path=tmp_output)

        reader = PdfReader(tmp_output)
        assert len(reader.pages) == 4

    def test_extract_single_page(self, sample_pdf, tmp_output):
        split_pdf(sample_pdf, [(3, 3)], merge=True, output_path=tmp_output)

        reader = PdfReader(tmp_output)
        assert len(reader.pages) == 1


class TestSplitPdfNoMerge:
    """Tests for split_pdf with merge=False."""

    def test_creates_zip(self, sample_pdf, tmp_path):
        output = tmp_path / "result.zip"
        result = split_pdf(sample_pdf, [(1, 2), (4, 5)], merge=False, output_path=output)

        assert result == output
        assert output.exists()
        assert zipfile.is_zipfile(output)

    def test_zip_contains_correct_files(self, sample_pdf, tmp_path):
        output = tmp_path / "result.zip"
        split_pdf(
            sample_pdf,
            [(1, 2), (4, 5)],
            merge=False,
            output_path=output,
            original_filename="test",
        )

        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert len(names) == 2
            assert "test_range_1-2.pdf" in names
            assert "test_range_4-5.pdf" in names

    def test_each_zip_entry_is_valid_pdf(self, sample_pdf, tmp_path):
        output = tmp_path / "result.zip"
        split_pdf(
            sample_pdf,
            [(1, 3)],
            merge=False,
            output_path=output,
            original_filename="doc",
        )

        with zipfile.ZipFile(output) as zf:
            for name in zf.namelist():
                data = zf.read(name)
                assert data[:5] == b"%PDF-"


class TestSplitPdfErrors:
    """Error cases for split_pdf."""

    def test_range_exceeds_page_count(self, sample_pdf, tmp_output):
        with pytest.raises(ValueError, match="exceeds PDF page count"):
            split_pdf(sample_pdf, [(1, 99)], merge=True, output_path=tmp_output)
