"""Register DejaVu Sans fonts for xhtml2pdf Unicode support."""

from pathlib import Path

from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import xhtml2pdf.default

_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

_registered = False


def register_fonts() -> None:
    """Register DejaVu Sans fonts with reportlab and xhtml2pdf.

    Safe to call multiple times — registration only happens once.
    """
    global _registered  # noqa: PLW0603
    if _registered:
        return

    # Register TTF fonts with reportlab
    pdfmetrics.registerFont(TTFont("DejaVuSans", str(_FONTS_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(
        TTFont("DejaVuSans-Bold", str(_FONTS_DIR / "DejaVuSans-Bold.ttf"))
    )
    pdfmetrics.registerFont(
        TTFont("DejaVuSans-Oblique", str(_FONTS_DIR / "DejaVuSans-Oblique.ttf"))
    )
    pdfmetrics.registerFont(
        TTFont("DejaVuSans-BoldOblique", str(_FONTS_DIR / "DejaVuSans-BoldOblique.ttf"))
    )
    pdfmetrics.registerFont(
        TTFont("DejaVuSansMono", str(_FONTS_DIR / "DejaVuSansMono.ttf"))
    )
    pdfmetrics.registerFont(
        TTFont("DejaVuSansMono-Bold", str(_FONTS_DIR / "DejaVuSansMono-Bold.ttf"))
    )

    # Set up font families so bold/italic variants resolve correctly
    addMapping("DejaVuSans", 0, 0, "DejaVuSans")
    addMapping("DejaVuSans", 1, 0, "DejaVuSans-Bold")
    addMapping("DejaVuSans", 0, 1, "DejaVuSans-Oblique")
    addMapping("DejaVuSans", 1, 1, "DejaVuSans-BoldOblique")
    addMapping("DejaVuSansMono", 0, 0, "DejaVuSansMono")
    addMapping("DejaVuSansMono", 1, 0, "DejaVuSansMono-Bold")
    addMapping("DejaVuSansMono", 0, 1, "DejaVuSansMono")
    addMapping("DejaVuSansMono", 1, 1, "DejaVuSansMono-Bold")

    # Register with xhtml2pdf's font lookup so CSS font-family names resolve
    font_map = xhtml2pdf.default.DEFAULT_FONT
    font_map["dejavusans"] = "DejaVuSans"
    font_map["dejavusans-bold"] = "DejaVuSans-Bold"
    font_map["dejavusans-oblique"] = "DejaVuSans-Oblique"
    font_map["dejavusans-boldoblique"] = "DejaVuSans-BoldOblique"
    font_map["dejavusansmono"] = "DejaVuSansMono"
    font_map["dejavusansmono-bold"] = "DejaVuSansMono-Bold"

    _registered = True
