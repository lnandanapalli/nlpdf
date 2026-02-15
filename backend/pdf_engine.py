"""PDF manipulation engine using pypdf library."""

from pathlib import Path

from pypdf import PdfReader, PdfWriter


def compress_pdf(input_path: Path, output_path: Path) -> dict[str, int | float]:
    """
    Compress a PDF file by optimizing content streams.

    Args:
        input_path: Path to input PDF file
        output_path: Path to save compressed PDF

    Returns:
        Dictionary with original_size, compressed_size, and compression_ratio
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page in reader.pages:
        page.compress_content_streams()
        writer.add_page(page)

    with open(output_path, "wb") as output_file:
        writer.write(output_file)

    original_size = input_path.stat().st_size
    compressed_size = output_path.stat().st_size
    compression_ratio = (compressed_size / original_size) * 100

    return {
        "original_size": original_size,
        "compressed_size": compressed_size,
        "compression_ratio": compression_ratio,
    }


def split_pdf(
    input_path: Path, page_ranges: list[tuple[int, int]], output_path: Path
) -> int:
    """
    Extract specific page ranges from a PDF.

    Args:
        input_path: Path to input PDF file
        page_ranges: List of (start, end) tuples (0-indexed, end exclusive)
        output_path: Path to save extracted pages

    Returns:
        Number of pages extracted
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()

    pages_added = 0
    for start, end in page_ranges:
        for page_num in range(start, end):
            if page_num < len(reader.pages):
                writer.add_page(reader.pages[page_num])
                pages_added += 1

    with open(output_path, "wb") as output_file:
        writer.write(output_file)

    return pages_added


def merge_pdfs(input_paths: list[Path], output_path: Path) -> int:
    """
    Merge multiple PDF files into one.

    Args:
        input_paths: List of paths to PDF files to merge
        output_path: Path to save merged PDF

    Returns:
        Total number of pages in merged PDF
    """
    writer = PdfWriter()
    total_pages = 0

    for pdf_path in input_paths:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            writer.add_page(page)
            total_pages += 1

    with open(output_path, "wb") as output_file:
        writer.write(output_file)

    return total_pages


def rotate_pdf(
    input_path: Path, rotation: int, page_indices: list[int] | None, output_path: Path
) -> int:
    """
    Rotate specific pages in a PDF.

    Args:
        input_path: Path to input PDF file
        rotation: Degrees to rotate (90, 180, 270, or -90, -180, -270)
        page_indices: List of page indices to rotate (0-indexed), None for all pages
        output_path: Path to save rotated PDF

    Returns:
        Number of pages rotated
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()

    pages_to_rotate = (
        set(page_indices) if page_indices is not None else set(range(len(reader.pages)))
    )
    pages_rotated = 0

    for page_index, page in enumerate(reader.pages):
        if page_index in pages_to_rotate:
            page = page.rotate(rotation)
            pages_rotated += 1
        writer.add_page(page)

    with open(output_path, "wb") as output_file:
        writer.write(output_file)

    return pages_rotated
