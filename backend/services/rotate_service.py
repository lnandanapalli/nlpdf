"""PDF rotation service."""

from pathlib import Path

from pypdf import PdfReader, PdfWriter

MAX_PDF_PAGES = 5000


def rotate_pdf(
    input_path: Path,
    rotation_specs: list[tuple[int, int]],
    output_path: Path,
) -> Path:
    """
    Rotate specific pages in a PDF with individual rotation settings.

    Args:
        input_path: Path to input PDF file
        rotation_specs: List of (page_num, angle) tuples (1-indexed, clockwise only)
                        Example: [(1, 90), (3, 180), (5, 270)]
                        - page_num: 1-indexed page number
                        - angle: rotation angle (90, 180, or 270 clockwise)
        output_path: Path to save rotated PDF

    Returns:
        Path to the rotated PDF file
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()
    total_pages = len(reader.pages)

    if total_pages > MAX_PDF_PAGES:
        raise ValueError(f"PDF exceeds maximum page count ({MAX_PDF_PAGES})")

    # Validate page numbers against actual PDF page count (1-indexed)
    for page_num, _ in rotation_specs:
        if page_num > total_pages:
            raise ValueError(f"Page number {page_num} exceeds PDF page count ({total_pages})")

    # Create a dict of page rotations (convert to 0-indexed)
    rotations = {}
    for page_num, angle in rotation_specs:
        # Convert 1-indexed to 0-indexed
        page_idx = page_num - 1
        rotations[page_idx] = angle

    # Process all pages
    for page_index, orig_page in enumerate(reader.pages):
        if page_index in rotations:
            rotated_page = orig_page.rotate(rotations[page_index])
            writer.add_page(rotated_page)
        else:
            writer.add_page(orig_page)

    with output_path.open("wb") as output_file:
        writer.write(output_file)

    return output_path
