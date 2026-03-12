"""Tests for the compress service."""

import io
from pathlib import Path

import pikepdf
from PIL import Image
from pypdf import PdfReader
import pytest

from backend.services.compress_service import compress_pdf


def _make_pdf_with_image(
    path: Path, width: int = 200, height: int = 200, mode: str = "RGB"
) -> Path:
    """Create a PDF containing an embedded image."""
    # Create a large-ish image so compression has something to work with
    img = Image.new(mode, (width, height), color="red")
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_buf.seek(0)

    # Build PDF with pikepdf and embed the image
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))

    raw_img = Image.open(img_buf)
    # Convert to RGB if needed for JPEG embedding
    if raw_img.mode != "RGB":
        rgb_img = raw_img.convert("RGB")
    else:
        rgb_img = raw_img

    jpeg_buf = io.BytesIO()
    rgb_img.save(jpeg_buf, format="JPEG", quality=95)
    jpeg_data = jpeg_buf.getvalue()

    image_stream = pikepdf.Stream(pdf, jpeg_data)
    image_stream["/Type"] = pikepdf.Name.XObject
    image_stream["/Subtype"] = pikepdf.Name.Image
    image_stream["/Width"] = width
    image_stream["/Height"] = height
    image_stream["/ColorSpace"] = pikepdf.Name.DeviceRGB
    image_stream["/BitsPerComponent"] = 8
    image_stream["/Filter"] = pikepdf.Name.DCTDecode

    page = pdf.pages[0]
    page_resources = pikepdf.Dictionary()
    xobject = pikepdf.Dictionary()
    xobject["/Im0"] = pdf.make_indirect(image_stream)
    page_resources["/XObject"] = xobject
    page["/Resources"] = page_resources

    # Add content stream that draws the image
    content = b"q 200 0 0 200 100 400 cm /Im0 Do Q"
    page["/Contents"] = pdf.make_indirect(pikepdf.Stream(pdf, content))

    pdf.save(path)
    return path


def _make_pdf_with_png_image(path: Path, width: int = 200, height: int = 200) -> Path:
    """Create a PDF containing a non-JPEG (FlateDecode) image."""
    img = Image.new("RGB", (width, height), color="blue")

    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))

    # Embed as raw uncompressed RGB (FlateDecode)
    raw_data = img.tobytes()
    import zlib

    compressed = zlib.compress(raw_data)

    image_stream = pikepdf.Stream(pdf, compressed)
    image_stream["/Type"] = pikepdf.Name.XObject
    image_stream["/Subtype"] = pikepdf.Name.Image
    image_stream["/Width"] = width
    image_stream["/Height"] = height
    image_stream["/ColorSpace"] = pikepdf.Name.DeviceRGB
    image_stream["/BitsPerComponent"] = 8
    image_stream["/Filter"] = pikepdf.Name.FlateDecode

    page = pdf.pages[0]
    page_resources = pikepdf.Dictionary()
    xobject = pikepdf.Dictionary()
    xobject["/Im0"] = pdf.make_indirect(image_stream)
    page_resources["/XObject"] = xobject
    page["/Resources"] = page_resources

    content = b"q 200 0 0 200 100 400 cm /Im0 Do Q"
    page["/Contents"] = pdf.make_indirect(pikepdf.Stream(pdf, content))

    pdf.save(path)
    return path


class TestCompressPdf:
    """Tests for compress_pdf."""

    @pytest.mark.parametrize("level", [1, 2, 3])
    def test_all_levels_produce_output(self, tmp_path, level):
        """Each compression level should produce a valid PDF."""
        input_path = _make_pdf_with_image(tmp_path / "input.pdf")
        output_path = tmp_path / f"compressed_{level}.pdf"

        result = compress_pdf(input_path, output_path, level)

        assert result == output_path
        assert output_path.exists()
        reader = PdfReader(output_path)
        assert len(reader.pages) == 1

    def test_higher_level_produces_smaller_file(self, tmp_path):
        """Level 3 should produce a smaller file than level 1."""
        input_path = _make_pdf_with_image(tmp_path / "input.pdf", width=400, height=400)
        out_low = tmp_path / "low.pdf"
        out_high = tmp_path / "high.pdf"

        compress_pdf(input_path, out_low, level=1)
        compress_pdf(input_path, out_high, level=3)

        assert out_high.stat().st_size <= out_low.stat().st_size

    def test_output_is_smaller_than_input(self, tmp_path):
        """Compressed PDF should be smaller than the original."""
        input_path = _make_pdf_with_image(tmp_path / "input.pdf", width=500, height=500)
        output_path = tmp_path / "compressed.pdf"
        original_size = input_path.stat().st_size

        compress_pdf(input_path, output_path, level=2)

        assert output_path.stat().st_size < original_size


class TestCompressPdfWithNonJpegImages:
    """Tests for compressing PDFs with non-JPEG (FlateDecode) images."""

    def test_png_image_gets_compressed(self, tmp_path):
        """Non-JPEG images should be converted to JPEG."""
        input_path = _make_pdf_with_png_image(tmp_path / "input.pdf", width=300, height=300)
        output_path = tmp_path / "compressed.pdf"

        result = compress_pdf(input_path, output_path, level=2)

        assert result == output_path
        assert output_path.exists()
        reader = PdfReader(output_path)
        assert len(reader.pages) == 1


class TestCompressPdfWithBlankPages:
    """Tests for compressing PDFs that have no images."""

    def test_blank_pdf_still_produces_output(self, sample_pdf, tmp_output):
        """A PDF with no images should still compress (stream compression)."""
        result = compress_pdf(sample_pdf, tmp_output, level=2)

        assert result == tmp_output
        assert tmp_output.exists()
        reader = PdfReader(tmp_output)
        assert len(reader.pages) == 5


class TestCompressPdfEdgeCases:
    """Edge cases for compress_pdf."""

    def test_small_image_skipped(self, tmp_path):
        """Images smaller than 50x50 should be skipped (not compressed)."""
        input_path = _make_pdf_with_image(tmp_path / "input.pdf", width=30, height=30)
        output_path = tmp_path / "compressed.pdf"

        # Should not raise, just skip the tiny image
        compress_pdf(input_path, output_path, level=3)
        assert output_path.exists()
