"""Markdown to PDF conversion service using markdown and xhtml2pdf."""

from pathlib import Path

import markdown
import nh3
import structlog
from xhtml2pdf import pisa

from backend.services.pdf_fonts import register_fonts

logger = structlog.get_logger(__name__)

CSS = """\
body {
    font-family: DejaVuSans;
    font-size: 12px;
    line-height: 1.6;
    color: #222;
    margin: 0;
}
h1 { font-size: 24px; margin-top: 24px; margin-bottom: 12px; }
h2 { font-size: 20px; margin-top: 20px; margin-bottom: 10px; }
h3 { font-size: 16px; margin-top: 16px; margin-bottom: 8px; }
h4, h5, h6 { font-size: 14px; margin-top: 14px; margin-bottom: 6px; }
p { margin: 8px 0; }
code {
    font-family: DejaVuSansMono;
    font-size: 11px;
    background-color: #f4f4f4;
    padding: 2px 4px;
}
pre {
    background-color: #f4f4f4;
    padding: 12px;
    margin: 12px 0;
    font-family: DejaVuSansMono;
    font-size: 11px;
    line-height: 1.4;
}
blockquote {
    border-left: 3px solid #ccc;
    margin: 12px 0;
    padding: 8px 16px;
    color: #555;
}
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
hr { border: none; border-top: 1px solid #ddd; margin: 16px 0; }
a { color: #0066cc; }
"""

PAPER_SIZES = {
    "A4": "@page { size: A4; margin: 2cm; }",
    "letter": "@page { size: letter; margin: 1in; }",
}


def markdown_to_pdf(input_path: Path, output_path: Path, paper_size: str = "A4") -> Path:
    """
    Convert a markdown file to PDF.

    Args:
        input_path: Path to the input markdown file.
        output_path: Path to save the output PDF.
        paper_size: Paper size — "A4" or "letter".

    Returns:
        Path to the generated PDF file.

    Raises:
        ValueError: If the markdown file cannot be read or converted.
    """
    register_fonts()

    md_text = input_path.read_text(encoding="utf-8")

    raw_html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "nl2br", "sane_lists"],
    )

    # Security: We only allow the strict subset of HTML tags that the Markdown library
    # mathematically generates for basic text formatting. If a user tries to write
    # ANY raw HTML (like <div>, <iframe>, <script>, <img>, <form>), it is instantly nuked.
    safe_markdown_tags = {
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "strong",
        "em",
        "code",
        "pre",
        "blockquote",
        "ul",
        "ol",
        "li",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "br",
        "hr",
        "a",
    }

    # We also strictly limit attributes to only what's necessary (e.g. href for links)
    safe_attributes = {"a": {"href", "title"}}

    html_body = nh3.clean(raw_html_body, tags=safe_markdown_tags, attributes=safe_attributes)

    page_css = PAPER_SIZES.get(paper_size, PAPER_SIZES["A4"])

    html = (
        "<!DOCTYPE html>"
        "<html><head><meta charset='utf-8'/>"
        f"<style>{page_css}\n{CSS}</style>"
        f"</head><body>{html_body}</body></html>"
    )

    with output_path.open("wb") as f:
        status = pisa.CreatePDF(html, dest=f)

    if status.err:
        output_path.unlink(missing_ok=True)
        raise ValueError(f"PDF conversion failed with {status.err} error(s)")

    logger.info(
        "Markdown converted to PDF",
        input=str(input_path),
        output=str(output_path),
        paper_size=paper_size,
    )

    return output_path
