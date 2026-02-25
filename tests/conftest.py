"""Shared pytest fixtures for the NLPDF test suite."""

from pathlib import Path

import pytest
from pypdf import PdfWriter


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    """Create a real 5-page PDF for testing."""
    pdf_path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    for _ in range(5):
        writer.add_blank_page(width=612, height=792)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


@pytest.fixture()
def small_pdf(tmp_path: Path) -> Path:
    """Create a single-page PDF for simple tests."""
    pdf_path = tmp_path / "small.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


@pytest.fixture()
def tmp_output(tmp_path: Path) -> Path:
    """Provide a temporary output path."""
    return tmp_path / "output.pdf"


@pytest.fixture()
def pdf_bytes(small_pdf: Path) -> bytes:
    """Return raw bytes of a valid single-page PDF."""
    return small_pdf.read_bytes()
