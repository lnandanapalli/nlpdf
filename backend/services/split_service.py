"""PDF splitting service."""

import zipfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def split_pdf(
    input_path: Path,
    page_ranges: list[tuple[int, int]],
    merge: bool,
    output_path: Path,
    original_filename: str = "document",
) -> Path:
    """
    Extract specific page ranges from a PDF.

    Args:
        input_path: Path to input PDF file
        page_ranges: List of (start, end) tuples (1-indexed, inclusive)
                     Example: [1, 5] means pages 1, 2, 3, 4, 5
        merge: If True, merge all ranges into one PDF; if False, create ZIP of
            separate PDFs
        output_path: Path to save the result (PDF if merge=True, ZIP if merge=False)
        original_filename: Original filename (without extension) for naming split files

    Returns:
        Path to the output file (PDF or ZIP)
    """
    reader = PdfReader(input_path)
    total_pages = len(reader.pages)

    if total_pages > 5000:
        raise ValueError("PDF exceeds maximum page count (5000)")

    # Validate ranges against actual PDF page count (1-indexed)
    for start, end in page_ranges:
        if end > total_pages:
            raise ValueError(
                f"Range [{start}, {end}] exceeds PDF page count ({total_pages})"
            )

    if merge:
        # Merge all ranges into a single PDF
        writer = PdfWriter()
        for start, end in page_ranges:
            # Convert from 1-indexed inclusive to 0-indexed for pypdf
            for page_num in range(start - 1, end):
                if page_num < len(reader.pages):
                    writer.add_page(reader.pages[page_num])

        with open(output_path, "wb") as output_file:
            writer.write(output_file)

        return output_path
    else:
        # Create separate PDFs for each range and zip them
        temp_dir = output_path.parent
        pdf_files = []

        for start, end in page_ranges:
            writer = PdfWriter()
            # Convert from 1-indexed inclusive to 0-indexed for pypdf
            for page_num in range(start - 1, end):
                if page_num < len(reader.pages):
                    writer.add_page(reader.pages[page_num])

            pdf_filename = f"{original_filename}_range_{start}-{end}.pdf"
            pdf_path = temp_dir / pdf_filename
            with open(pdf_path, "wb") as pdf_file:
                writer.write(pdf_file)
            pdf_files.append(pdf_path)

        # Create ZIP file
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for path in pdf_files:
                zipf.write(path, path.name)
                path.unlink()  # Delete temporary PDF file

        return output_path
