"""PDF merging service."""

from pathlib import Path

from pypdf import PdfReader, PdfWriter

MAX_PDF_PAGES = 5000


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
    total_pages = 0

    for pdf_path in input_paths:
        reader = PdfReader(pdf_path)
        total_pages += len(reader.pages)
        if total_pages > MAX_PDF_PAGES:
            raise ValueError(f"Combined PDFs exceed maximum page count ({MAX_PDF_PAGES})")
        for page in reader.pages:
            writer.add_page(page)

    with output_path.open("wb") as output_file:
        writer.write(output_file)

    return output_path
