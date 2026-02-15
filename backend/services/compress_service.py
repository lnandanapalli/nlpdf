"""PDF compression service."""

from pathlib import Path

from pypdf import PdfReader, PdfWriter


def compress_pdf(input_path: Path, output_path: Path) -> Path:
    """
    Compress a PDF file by optimizing content streams.

    Args:
        input_path: Path to input PDF file
        output_path: Path to save compressed PDF

    Returns:
        Path to the compressed PDF file
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    for page in writer.pages:
        page.compress_content_streams()

    with open(output_path, "wb") as output_file:
        writer.write(output_file)

    return output_path
