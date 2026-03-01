"""Word (DOCX) to PDF conversion service using mammoth and xhtml2pdf."""

import structlog
from pathlib import Path

import mammoth
from xhtml2pdf import pisa

logger = structlog.get_logger(__name__)

CSS = """\
body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 12px;
    line-height: 1.6;
    color: #222;
    margin: 40px;
}
h1 { font-size: 24px; margin-top: 24px; margin-bottom: 12px; }
h2 { font-size: 20px; margin-top: 20px; margin-bottom: 10px; }
h3 { font-size: 16px; margin-top: 16px; margin-bottom: 8px; }
h4, h5, h6 { font-size: 14px; margin-top: 14px; margin-bottom: 6px; }
p { margin: 8px 0; }
table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
}
th, td {
    border: 1px solid #ddd;
    padding: 8px;
    text-align: left;
}
th {
    background-color: #f4f4f4;
    font-weight: bold;
}
ul, ol { margin: 8px 0; padding-left: 24px; }
li { margin: 4px 0; }
a { color: #0066cc; }
"""

PAPER_SIZES = {
    "A4": "@page { size: A4; margin: 2cm; }",
    "letter": "@page { size: letter; margin: 1in; }",
}


def word_to_pdf(input_path: Path, output_path: Path, paper_size: str = "A4") -> Path:
    """
    Convert a Word (DOCX) file to PDF.

    Uses mammoth to extract semantic HTML from the DOCX, then
    xhtml2pdf to render the HTML as a PDF.

    Args:
        input_path: Path to the input DOCX file.
        output_path: Path to save the output PDF.
        paper_size: Paper size — "A4" or "letter".

    Returns:
        Path to the generated PDF file.

    Raises:
        ValueError: If the DOCX file cannot be read or converted.
    """
    with open(input_path, "rb") as f:
        result = mammoth.convert_to_html(f)

    html_body = result.value

    if result.messages:
        for msg in result.messages:
            logger.debug("mammoth: %s", msg)

    page_css = PAPER_SIZES.get(paper_size, PAPER_SIZES["A4"])

    html = (
        "<!DOCTYPE html>"
        "<html><head><meta charset='utf-8'/>"
        f"<style>{page_css}\n{CSS}</style>"
        f"</head><body>{html_body}</body></html>"
    )

    with open(output_path, "wb") as f:
        status = pisa.CreatePDF(html, dest=f)

    if status.err:
        output_path.unlink(missing_ok=True)
        raise ValueError(f"PDF conversion failed with {status.err} error(s)")

    logger.info(
        "Word converted to PDF",
        input=str(input_path),
        output=str(output_path),
        paper_size=paper_size,
    )

    return output_path
