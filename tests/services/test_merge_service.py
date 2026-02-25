"""Tests for the merge service."""

from pypdf import PdfReader, PdfWriter

from backend.services.merge_service import merge_pdfs


def _make_pdf(path, pages: int = 1):
    """Helper to create a PDF with a given number of blank pages."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with open(path, "wb") as f:
        writer.write(f)
    return path


class TestMergePdfs:
    """Tests for merge_pdfs."""

    def test_merge_two_pdfs(self, tmp_path):
        pdf1 = _make_pdf(tmp_path / "a.pdf", pages=2)
        pdf2 = _make_pdf(tmp_path / "b.pdf", pages=3)
        output = tmp_path / "merged.pdf"

        result = merge_pdfs([pdf1, pdf2], output)

        assert result == output
        assert output.exists()
        reader = PdfReader(output)
        assert len(reader.pages) == 5

    def test_merge_three_pdfs(self, tmp_path):
        pdfs = [_make_pdf(tmp_path / f"{i}.pdf", pages=1) for i in range(3)]
        output = tmp_path / "merged.pdf"

        merge_pdfs(pdfs, output)

        reader = PdfReader(output)
        assert len(reader.pages) == 3

    def test_merge_preserves_page_order(self, tmp_path):
        pdf1 = _make_pdf(tmp_path / "a.pdf", pages=2)
        pdf2 = _make_pdf(tmp_path / "b.pdf", pages=1)
        output = tmp_path / "merged.pdf"

        merge_pdfs([pdf1, pdf2], output)

        reader = PdfReader(output)
        assert len(reader.pages) == 3
