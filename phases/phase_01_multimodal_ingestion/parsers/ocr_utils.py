"""OCR helpers for scanned PDF pages and figure images."""

from __future__ import annotations

from pathlib import Path

_ocr_checked = False
_ocr_available = False


def ocr_available() -> bool:
    """Return True when pytesseract and the Tesseract binary are usable."""
    global _ocr_checked, _ocr_available
    if _ocr_checked:
        return _ocr_available
    _ocr_checked = True
    try:
        import pytesseract
        from PIL import Image

        pytesseract.get_tesseract_version()
        with Image.new("RGB", (8, 8), color="white") as probe:
            pytesseract.image_to_string(probe)
        _ocr_available = True
    except Exception:
        _ocr_available = False
    return _ocr_available


def ocr_image(image_path: Path, *, lang: str = "eng") -> str:
    """Run OCR on a PNG/JPEG; returns empty string when OCR is unavailable."""
    if not ocr_available():
        return ""
    try:
        import pytesseract
        from PIL import Image

        return pytesseract.image_to_string(Image.open(image_path), lang=lang).strip()
    except Exception:
        return ""
