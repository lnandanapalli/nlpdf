"""PDF merging service."""

from pathlib import Path

from pypdf import PdfReader, PdfWriter


def merge_pdfs(input_paths: list[Path], output_path: Path) -> Path:
    """
    Merge multiple PDF files into one.

    Args:
        input_paths: List of paths to PDF files to merge
        output_path: Path to save merged PDF

    Returns:
        Path to the merged PDF file
    """
    writer = PdfWriter()

    for pdf_path in input_paths:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            writer.add_page(page)

    with open(output_path, "wb") as output_file:
        writer.write(output_file)

    return output_path
