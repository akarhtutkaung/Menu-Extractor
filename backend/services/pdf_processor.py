# from __future__ import annotations

# import base64
# import logging

# import fitz  # PyMuPDF

# log = logging.getLogger(__name__)

# _MEANINGFUL_CHAR_THRESHOLD = 50

# _LOSSLESS_FILTERS = {"FlateDecode", "LZWDecode", "RunLengthDecode", "CCITTFaxDecode", ""}


# def _render_params_for_page(page) -> tuple[int, int, str]:
#     """Return (dpi, jpeg_quality, label) based on actual image quality signals.

#     Four signals are scored per embedded image:
#       1. Compression filter — lossless beats JPEG
#       2. Bits per component — higher depth = more detail
#       3. Pixel dimensions   — larger = more information
#       4. Image-to-page area ratio — thumbnail vs full-page coverage
#     The maximum score across all images drives the render tier.
#     """
#     embedded = page.get_images(full=True)
#     if not embedded:
#         return 96, 82, "scan"

#     page_area = page.rect.width * page.rect.height or 1  # avoid div-by-zero

#     best = 0
#     for img in embedded:
#         w, h, bpc, fltr = img[2], img[3], img[4], img[8]

#         # Signal 1: compression filter
#         if fltr in _LOSSLESS_FILTERS:
#             s_filter = 3
#         elif fltr == "JPXDecode":
#             s_filter = 1
#         else:  # DCTDecode and anything unknown
#             s_filter = 0

#         # Signal 2: bits per component
#         if bpc >= 16:
#             s_bpc = 2
#         elif bpc >= 8:
#             s_bpc = 1
#         else:
#             s_bpc = 0

#         # Signal 3: pixel dimensions
#         max_dim = max(w, h)
#         if max_dim >= 4000:
#             s_dim = 3
#         elif max_dim >= 2000:
#             s_dim = 2
#         elif max_dim >= 800:
#             s_dim = 1
#         else:
#             s_dim = 0

#         # Signal 4: image-to-page coverage ratio
#         ratio = (w * h) / page_area
#         if ratio >= 0.50:
#             s_ratio = 2
#         elif ratio >= 0.10:
#             s_ratio = 1
#         else:
#             s_ratio = 0

#         score = s_filter + s_bpc + s_dim + s_ratio
#         if score > best:
#             best = score

#     if best >= 7:
#         return 200, 92, "hires"
#     if best >= 5:
#         return 150, 88, "camera"
#     if best >= 3:
#         return 120, 85, "mixed"
#     return 96, 82, "scan"


# def _is_meaningful(text: str) -> bool:
#     """Return True if text contains enough non-whitespace characters."""
#     stripped = "".join(ch for ch in text if not ch.isspace())
#     return len(stripped) >= _MEANINGFUL_CHAR_THRESHOLD


# def extract_content(file_bytes: bytes) -> dict:
#     """Extract text and/or page images from a PDF.

#     Returns a dict with keys:
#         "text"   — concatenated text from all pages (may be empty string)
#         "images" — list of base64-encoded JPEG strings, one per page
#                    (populated only when the text heuristic deems it image-based)
#     """
#     doc = fitz.open(stream=file_bytes, filetype="pdf")
#     page_count = doc.page_count
#     log.info("Opened PDF: %d page(s)", page_count)

#     all_text_parts: list[str] = []
#     for i, page in enumerate(doc):
#         page_text = page.get_text()
#         log.debug("Page %d: %d chars extracted", i + 1, len(page_text))
#         all_text_parts.append(page_text)

#     combined_text = "\n".join(all_text_parts)
#     meaningful_chars = len("".join(ch for ch in combined_text if not ch.isspace()))
#     log.info("Text extraction: %d meaningful chars (threshold=%d)", meaningful_chars, _MEANINGFUL_CHAR_THRESHOLD)

#     if _is_meaningful(combined_text):
#         log.info("Using TEXT path")
#         doc.close()
#         return {"text": combined_text, "images": []}

#     log.info("Using IMAGE path: rendering %d page(s) as adaptive JPEG", page_count)
#     images: list[str] = []
#     doc2 = fitz.open(stream=file_bytes, filetype="pdf")
#     for i, page in enumerate(doc2):
#         dpi, quality, label = _render_params_for_page(page)
#         pixmap = page.get_pixmap(dpi=dpi)
#         jpeg_bytes = pixmap.tobytes("jpeg", jpg_quality=quality)
#         encoded = base64.b64encode(jpeg_bytes).decode("utf-8")
#         log.info("Page %d rendered: %.1f KB JPEG (%s, dpi=%d, quality=%d)",
#                  i + 1, len(jpeg_bytes) / 1024, label, dpi, quality)
#         images.append(encoded)

#     doc2.close()
#     doc.close()
#     return {"text": "", "images": images}

from __future__ import annotations

import base64
import logging
from typing import NamedTuple

import fitz

log = logging.getLogger(__name__)

_MIN_CHARS_PER_PAGE: int = 100
_LOSSLESS_FILTERS: frozenset[str] = frozenset(
    {"FlateDecode", "LZWDecode", "RunLengthDecode", "CCITTFaxDecode", ""}
)
_DPI_MIN: int = 96
_DPI_MAX: int = 300
_FULL_BLEED_RATIO: float = 0.80
_RECOMPRESS_QUALITY: int = 75


class _RenderParams(NamedTuple):
    dpi: int
    quality: int
    label: str
    score: int


def _meaningful_chars(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def _text_coverage(pages: list[fitz.Page]) -> float:
    if not pages:
        return 0.0
    return sum(_meaningful_chars(p.get_text()) for p in pages) / len(pages)


def _score_image(w: int, h: int, bpc: int, fltr: str, page_area: float) -> int:
    if fltr in _LOSSLESS_FILTERS:
        s_filter = 3
    elif fltr == "JPXDecode":
        s_filter = 1
    else:
        s_filter = 0

    if bpc >= 16:
        s_bpc = 2
    elif bpc >= 8:
        s_bpc = 1
    else:
        s_bpc = 0

    max_dim = max(w, h)
    if max_dim >= 4000:
        s_dim = 3
    elif max_dim >= 2000:
        s_dim = 2
    elif max_dim >= 800:
        s_dim = 1
    else:
        s_dim = 0

    ratio = (w * h) / page_area
    if ratio >= 0.50:
        s_ratio = 2
    elif ratio >= 0.10:
        s_ratio = 1
    else:
        s_ratio = 0

    return s_filter + s_bpc + s_dim + s_ratio


def _render_params_for_page(page: fitz.Page) -> _RenderParams:
    embedded = page.get_images(full=True)
    if not embedded:
        return _RenderParams(96, 75, "scan", 0)

    page_area = (page.rect.width * page.rect.height) or 1.0
    best_score: int = 0
    best_w: int = 0

    for img in embedded:
        fields = img + (None,) * 10
        w, h, bpc, fltr = fields[2], fields[3], fields[4], fields[8]

        if not (isinstance(w, int) and isinstance(h, int)):
            log.debug("Skipping image with non-integer dimensions: %s", img)
            continue

        score = _score_image(
            w=w,
            h=h,
            bpc=int(bpc) if isinstance(bpc, int) else 8,
            fltr=str(fltr) if fltr is not None else "",
            page_area=page_area,
        )

        if score > best_score:
            best_score = score
            best_w = w

    if best_score >= 7 and best_w > 0:
        native_dpi = int((best_w / page.rect.width) * 72)
        native_dpi = max(_DPI_MIN, min(native_dpi, _DPI_MAX))
        return _RenderParams(native_dpi, 70, f"hires(native={native_dpi}dpi)", best_score)

    if best_score >= 5:
        return _RenderParams(150, 88, "camera", best_score)

    if best_score >= 3:
        return _RenderParams(120, 82, "mixed", best_score)

    return _RenderParams(96, 75, "scan", best_score)


def _try_direct_extract(page: fitz.Page, index: int) -> str | None:
    embedded = page.get_images(full=True)
    if not embedded:
        return None

    page_area = (page.rect.width * page.rect.height) or 1.0

    best = max(
        (img for img in embedded if isinstance(img[2], int) and isinstance(img[3], int)),
        key=lambda img: img[2] * img[3],
        default=None,
    )
    if best is None:
        return None

    w, h = best[2], best[3]
    ratio = (w * h) / page_area
    if ratio < _FULL_BLEED_RATIO:
        return None

    xref = best[0]
    try:
        img_data = page.parent.extract_image(xref)
        raw_bytes = img_data["image"]
        ext = img_data["ext"]

        if ext == "jpeg":
            pix = fitz.Pixmap(raw_bytes)
            jpeg_bytes = pix.tobytes("jpeg", jpg_quality=_RECOMPRESS_QUALITY)
            log.info(
                "Page %d direct: %.1f KB → %.1f KB JPEG (recompressed q%d, w=%d h=%d)",
                index + 1,
                len(raw_bytes) / 1024,
                len(jpeg_bytes) / 1024,
                _RECOMPRESS_QUALITY,
                w,
                h,
            )
            return base64.b64encode(jpeg_bytes).decode("utf-8")

        pix = fitz.Pixmap(raw_bytes)
        if pix.alpha:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        jpeg_bytes = pix.tobytes("jpeg", jpg_quality=85)
        log.info(
            "Page %d direct: %.1f KB %s → %.1f KB JPEG (converted, w=%d h=%d)",
            index + 1,
            len(raw_bytes) / 1024,
            ext.upper(),
            len(jpeg_bytes) / 1024,
            w,
            h,
        )
        return base64.b64encode(jpeg_bytes).decode("utf-8")

    except Exception as exc:
        log.warning("Page %d direct extract failed (%s) — will fall back to render", index + 1, exc)
        return None


def _render_page(page: fitz.Page, index: int) -> str:
    try:
        params = _render_params_for_page(page)
        pixmap = page.get_pixmap(dpi=params.dpi)
        jpeg_bytes = pixmap.tobytes("jpeg", jpg_quality=params.quality)
        log.info(
            "Page %d rendered: %.1f KB JPEG (%s, dpi=%d, quality=%d, score=%d)",
            index + 1,
            len(jpeg_bytes) / 1024,
            params.label,
            params.dpi,
            params.quality,
            params.score,
        )
        return base64.b64encode(jpeg_bytes).decode("utf-8")

    except Exception as exc:
        log.warning(
            "Page %d adaptive render failed (%s) — falling back to 96 DPI / q82",
            index + 1,
            exc,
        )
        pixmap = page.get_pixmap(dpi=_DPI_MIN)
        jpeg_bytes = pixmap.tobytes("jpeg", jpg_quality=82)
        return base64.b64encode(jpeg_bytes).decode("utf-8")


def _process_page(page: fitz.Page, index: int) -> str:
    result = _try_direct_extract(page, index)
    if result is not None:
        return result
    return _render_page(page, index)


def extract_content(file_bytes: bytes) -> dict:
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        page_count = doc.page_count
        log.info("Opened PDF: %d page(s)", page_count)

        pages: list[fitz.Page] = list(doc)

        coverage = _text_coverage(pages)
        log.info(
            "Text coverage: %.1f chars/page (threshold=%d)",
            coverage,
            _MIN_CHARS_PER_PAGE,
        )

        if coverage >= _MIN_CHARS_PER_PAGE:
            log.info("Using TEXT path")
            return {"text": "\n".join(p.get_text() for p in pages), "images": []}

        log.info("Using IMAGE path: rendering %d page(s) as adaptive JPEG", page_count)
        images = [_process_page(page, i) for i, page in enumerate(pages)]
        return {"text": "", "images": images}