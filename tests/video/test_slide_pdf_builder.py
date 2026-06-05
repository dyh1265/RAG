"""Tests for slides.pdf assembly."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from backend.video.models import SlideFrame
from backend.video.slide_pdf_builder import build_slides_pdf


def test_build_slides_pdf_writes_one_page_per_slide(tmp_path: Path):
    slides_dir = tmp_path / "slides"
    slides_dir.mkdir()
    images: list[SlideFrame] = []
    for idx in range(2):
        path = slides_dir / f"slide_{idx + 1}.png"
        Image.new("RGB", (200, 120), (idx * 80, 40, 120)).save(path)
        images.append(SlideFrame(image_path=path, timestamp=float(idx * 2), slide_number=idx + 1))

    pdf_path = tmp_path / "slides.pdf"
    build_slides_pdf(images, pdf_path)

    assert pdf_path.is_file()
    assert pdf_path.stat().st_size > 0

    import fitz

    with fitz.open(str(pdf_path)) as doc:
        assert doc.page_count == 2
