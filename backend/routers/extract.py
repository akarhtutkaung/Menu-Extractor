from __future__ import annotations

import logging

import openai
from fastapi import APIRouter, UploadFile
from fastapi.responses import JSONResponse

from backend.config import MAX_FILE_SIZE_MB
from backend.services import image_processor, openai_client, pdf_processor

router = APIRouter()
log = logging.getLogger(__name__)

_MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}
_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


@router.post("/extract")
async def extract(file: UploadFile) -> JSONResponse:
    filename = file.filename or "unknown"
    content_type = (file.content_type or "").lower()
    log.info("Received upload: filename=%s content_type=%s", filename, content_type)

    # Validate content type
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if content_type not in _ALLOWED_CONTENT_TYPES and extension not in _ALLOWED_EXTENSIONS:
        log.warning("Rejected: invalid file type (filename=%s, content_type=%s)", filename, content_type)
        return _error("invalid_file_type", "Only PDF, JPG, and PNG files are accepted.", 400)

    is_image = content_type in _IMAGE_CONTENT_TYPES or extension in _IMAGE_EXTENSIONS

    # Read file bytes
    file_bytes = await file.read()
    size_kb = len(file_bytes) / 1024
    log.info("File read: %.1f KB", size_kb)

    # Validate file size
    if len(file_bytes) > _MAX_FILE_SIZE_BYTES:
        log.warning("Rejected: file too large (%.1f KB > %d MB limit)", size_kb, MAX_FILE_SIZE_MB)
        return _error("file_too_large", f"File exceeds the maximum allowed size of {MAX_FILE_SIZE_MB} MB.", 400)

    # Extract content
    if is_image:
        log.info("Starting image extraction...")
        try:
            content = image_processor.extract_content(file_bytes, media_type=content_type)
        except Exception as exc:
            log.error("Image extraction failed: %s", exc, exc_info=True)
            return _error("extraction_failed", f"Could not process the image file: {exc}", 500)
        log.info("Image extracted: %.1f KB", len(file_bytes) / 1024)
    else:
        log.info("Starting PDF extraction...")
        try:
            content = pdf_processor.extract_content(file_bytes)
        except Exception as exc:
            log.error("PDF extraction failed: %s", exc, exc_info=True)
            return _error("extraction_failed", f"Could not process the PDF file: {exc}", 500)

    mode = "image" if content["images"] else "text"
    log.info(
        "Extracted: mode=%s text_chars=%d image_pages=%d",
        mode, len(content["text"]), len(content["images"]),
    )

    # Call OpenAI
    log.info("Calling OpenAI (mode=%s)...", mode)
    try:
        menu_response = await openai_client.extract_menu(content)
    except openai.APITimeoutError:
        log.error("OpenAI request timed out")
        return _error("timeout", "The extraction request timed out. Please try again.", 504)
    except Exception as exc:
        log.error("OpenAI extraction failed: %s", exc, exc_info=True)
        return _error("extraction_failed", f"Menu extraction failed: {exc}", 500)

    total_items = sum(len(cat.items) for cat in menu_response.categories)
    log.info(
        "Extraction complete: restaurant=%r language=%s categories=%d items=%d",
        menu_response.restaurant_name,
        menu_response.language_code,
        len(menu_response.categories),
        total_items,
    )

    return JSONResponse(content=menu_response.model_dump())
    # return JSONResponse(content={"message": "PDF extracted successfully", "content": content})
