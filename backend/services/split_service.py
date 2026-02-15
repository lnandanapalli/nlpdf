"""PDF splitting service."""

from pathlib import Path

from pypdf import PdfReader, PdfWriter


def split_pdf(
    input_path: Path, page_ranges: list[tuple[int, int]], output_path: Path
) -> Path:
    """
    Extract specific page ranges from a PDF.

    Args:
        input_path: Path to input PDF file
        page_ranges: List of (start, end) tuples (0-indexed, end exclusive)
        output_path: Path to save extracted pages

    Returns:
        Path to the split PDF file
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()

    for start, end in page_ranges:
        for page_num in range(start, end):
            if page_num < len(reader.pages):
                writer.add_page(reader.pages[page_num])

    with open(output_path, "wb") as output_file:
        writer.write(output_file)

    return output_path
