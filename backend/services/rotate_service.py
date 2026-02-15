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
        page_indices: Page indices to rotate (1-indexed), None for all pages
                      Example: [1, 3, 5] means pages 1, 3, and 5
        output_path: Path to save rotated PDF

    Returns:
        Path to the rotated PDF file
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()
    total_pages = len(reader.pages)

    # Validate page indices against actual PDF page count (1-indexed)
    if page_indices is not None:
        for idx in page_indices:
            if idx > total_pages:
                raise ValueError(
                    f"Page index {idx} exceeds PDF page count ({total_pages})"
                )

    # Convert 1-indexed to 0-indexed for pypdf
    pages_to_rotate = (
        set(idx - 1 for idx in page_indices)
        if page_indices is not None
        else set(range(total_pages))
    )

    for page_index, page in enumerate(reader.pages):
        if page_index in pages_to_rotate:
            page = page.rotate(rotation)
        writer.add_page(page)

    with open(output_path, "wb") as output_file:
        writer.write(output_file)

    return output_path
