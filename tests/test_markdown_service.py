"""Tests for markdown to PDF conversion service."""

from pathlib import Path

import pytest

from backend.services.markdown_service import markdown_to_pdf


@pytest.fixture
def md_file(tmp_path: Path) -> Path:
    """Create a sample markdown file."""
    md_path = tmp_path / "sample.md"
    md_path.write_text(
        "# Hello World\n\n"
        "This is a **bold** and *italic* paragraph.\n\n"
        "## Lists\n\n"
        "- Item one\n"
        "- Item two\n"
        "- Item three\n\n"
        "1. First\n"
        "2. Second\n",
        encoding="utf-8",
    )
    return md_path


@pytest.fixture
def md_with_tables(tmp_path: Path) -> Path:
    """Create a markdown file with tables and code blocks."""
    md_path = tmp_path / "tables.md"
    md_path.write_text(
        "# Report\n\n"
        "| Name | Value |\n"
        "|------|-------|\n"
        "| A    | 100   |\n"
        "| B    | 200   |\n\n"
        "```python\n"
        "def hello():\n"
        '    print("world")\n'
        "```\n",
        encoding="utf-8",
    )
    return md_path


class TestMarkdownToPdf:
    """Tests for markdown_to_pdf."""

    def test_basic_conversion(self, md_file: Path, tmp_path: Path):
        output = tmp_path / "output.pdf"
        result = markdown_to_pdf(md_file, output)

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0
        # Verify it's a real PDF
        assert output.read_bytes()[:5] == b"%PDF-"

    def test_tables_and_code(self, md_with_tables: Path, tmp_path: Path):
        output = tmp_path / "output.pdf"
        result = markdown_to_pdf(md_with_tables, output)

        assert result == output
        assert output.exists()
        assert output.read_bytes()[:5] == b"%PDF-"

    def test_letter_paper_size(self, md_file: Path, tmp_path: Path):
        output = tmp_path / "output.pdf"
        result = markdown_to_pdf(md_file, output, paper_size="letter")

        assert result == output
        assert output.exists()
        assert output.read_bytes()[:5] == b"%PDF-"

    def test_empty_markdown(self, tmp_path: Path):
        md_path = tmp_path / "empty.md"
        md_path.write_text("", encoding="utf-8")
        output = tmp_path / "output.pdf"

        # Empty markdown should still produce a valid (blank) PDF
        result = markdown_to_pdf(md_path, output)
        assert result == output
        assert output.exists()
