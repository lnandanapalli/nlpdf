"""PDF compression service using pikepdf and Pillow."""

import io
import structlog
from pathlib import Path

import pikepdf
from pikepdf import Stream
from PIL import Image

logger = structlog.get_logger(__name__)

# Level -> scale factor (how much of original to keep)
SCALE_FACTORS = {1: 0.6, 2: 0.4, 3: 0.2}
JPEG_QUALITY = 40


def compress_pdf(input_path: Path, output_path: Path, level: int) -> Path:
    """
    Compress a PDF by downscaling images and compressing streams.

    Args:
        input_path: Path to input PDF file
        output_path: Path to save compressed PDF
        level: Compression level (1=low, 2=medium, 3=high)

    Returns:
        Path to the compressed PDF file
    """
    scale = SCALE_FACTORS[level]

    with pikepdf.open(input_path) as pdf:
        if len(pdf.pages) > 5000:
            raise ValueError("PDF exceeds maximum page count (5000)")

        for page in pdf.pages:
            _compress_page_images(page, scale)

        pdf.save(output_path, compress_streams=True)

    return output_path


def _compress_page_images(page: pikepdf.Page, scale: float) -> None:
    """Compress all images on a page."""
    try:
        images = page.images
    except Exception:
        return

    for name in list(images.keys()):
        try:
            raw_stream: Stream = images[name]  # type: ignore[assignment]
            pdf_image = pikepdf.PdfImage(raw_stream)

            if pdf_image.width < 50 or pdf_image.height < 50:
                continue

            current_filter = raw_stream.get("/Filter")
            if current_filter == pikepdf.Name.DCTDecode:
                _recompress_jpeg(raw_stream, pdf_image, scale)
            else:
                _compress_to_jpeg(raw_stream, pdf_image, scale)

        except Exception as e:
            logger.debug(
                "Failed to compress image '%s': %s: %s",
                name,
                type(e).__name__,
                e,
            )
            continue


def _recompress_jpeg(raw_stream, pdf_image, scale: float) -> None:
    """Recompress an existing JPEG image."""
    raw_bytes = raw_stream.read_raw_bytes()
    original_size = len(bytes(raw_bytes))
    pil_image = Image.open(io.BytesIO(raw_bytes))

    new_w = max(1, int(pil_image.width * scale))
    new_h = max(1, int(pil_image.height * scale))
    resized_image = pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    resized_image.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    jpeg_data = buf.getvalue()

    if len(jpeg_data) >= original_size:
        return

    logger.debug("JPEG recompressed: %d -> %d bytes", original_size, len(jpeg_data))
    raw_stream.write(jpeg_data, filter=pikepdf.Name.DCTDecode)
    raw_stream.Width = new_w
    raw_stream.Height = new_h


def _compress_to_jpeg(raw_stream, pdf_image, scale: float) -> None:
    """Compress a non-JPEG image to JPEG."""
    pil_image = pdf_image.as_pil_image()

    if pil_image.mode not in ("RGB", "L", "LA", "RGBA"):
        return

    if pil_image.mode in ("RGBA", "LA"):
        pil_image = pil_image.convert("RGB" if pil_image.mode == "RGBA" else "L")

    original_size = len(bytes(raw_stream.read_raw_bytes()))

    new_w = max(1, int(pil_image.width * scale))
    new_h = max(1, int(pil_image.height * scale))
    resized_image = pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    resized_image.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    jpeg_data = buf.getvalue()

    if len(jpeg_data) >= original_size:
        return

    logger.debug("Converted to JPEG: %d -> %d bytes", original_size, len(jpeg_data))

    for old_key in ["/DecodeParms", "/Decode", "/SMask", "/Mask"]:
        if old_key in raw_stream:
            del raw_stream[old_key]

    raw_stream.write(jpeg_data, filter=pikepdf.Name.DCTDecode)
    if pil_image.mode == "L":
        raw_stream.ColorSpace = pikepdf.Name.DeviceGray
    else:
        raw_stream.ColorSpace = pikepdf.Name.DeviceRGB
    raw_stream.BitsPerComponent = 8
    raw_stream.Width = new_w
    raw_stream.Height = new_h
