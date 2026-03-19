from __future__ import annotations

import base64
import logging

import fitz

log = logging.getLogger(__name__)

_JPEG_QUALITY = 85


def extract_content(file_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """Wrap a single uploaded image in the same content dict used by the PDF path.

    Normalises to JPEG so the OpenAI vision call always receives a consistent format.
    Returns {"text": "", "images": [<base64-jpeg-string>]}.
    """
    try:
        pix = fitz.Pixmap(file_bytes)
    except Exception as exc:
        raise ValueError(f"Could not decode image: {exc}") from exc

    if pix.alpha:
        pix = fitz.Pixmap(fitz.csRGB, pix)

    jpeg_bytes = pix.tobytes("jpeg", jpg_quality=_JPEG_QUALITY)
    log.info(
        "Image normalised: %.1f KB %s → %.1f KB JPEG (q%d, w=%d h=%d)",
        len(file_bytes) / 1024,
        media_type,
        len(jpeg_bytes) / 1024,
        _JPEG_QUALITY,
        pix.width,
        pix.height,
    )

    return {"text": "", "images": [base64.b64encode(jpeg_bytes).decode("utf-8")]}
