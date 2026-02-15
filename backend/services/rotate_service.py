"""PDF rotation service."""

from pathlib import Path

from pypdf import PdfReader, PdfWriter


def rotate_pdf(
    input_path: Path,
    rotation: int,
    page_indices: list[int] | None,
    output_path: Path,
) -> Path:
    """
    Rotate specific pages in a PDF.

    Args:
        input_path: Path to input PDF file
        rotation: Degrees to rotate (90, 180, 270, or negative)
        page_indices: Page indices to rotate (0-indexed), None for all pages
        output_path: Path to save rotated PDF

    Returns:
        Path to the rotated PDF file
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()

    pages_to_rotate = (
        set(page_indices) if page_indices is not None else set(range(len(reader.pages)))
    )

    for page_index, page in enumerate(reader.pages):
        if page_index in pages_to_rotate:
            page = page.rotate(rotation)
        writer.add_page(page)

    with open(output_path, "wb") as output_file:
        writer.write(output_file)

    return output_path
