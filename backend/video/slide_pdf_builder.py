"""Build a PDF document from extracted slide images."""

from __future__ import annotations

from pathlib import Path

from backend.video.models import SlideFrame


class SlidePDFBuildError(RuntimeError):
    """Raised when slide images cannot be assembled into a PDF."""


def build_slides_pdf(slides: list[SlideFrame], out_path: Path) -> Path:
    """Combine unique slide PNGs into a single PDF (one page per slide)."""
    try:
        import fitz
    except ImportError as exc:
        raise SlidePDFBuildError(
            "PyMuPDF is required to build slides.pdf (pip install pymupdf)"
        ) from exc

    if not slides:
        raise SlidePDFBuildError("No slides to include in PDF")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()

    try:
        for slide in slides:
            if not slide.image_path.is_file():
                raise SlidePDFBuildError(f"Slide image missing: {slide.image_path}")

            pixmap = fitz.Pixmap(str(slide.image_path))
            width, height = pixmap.width, pixmap.height
            pixmap = None

            page = doc.new_page(width=width, height=height)
            page.insert_image(page.rect, filename=str(slide.image_path))

        doc.save(str(out_path))
    finally:
        doc.close()

    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise SlidePDFBuildError(f"Failed to write slides PDF: {out_path}")

    return out_path
