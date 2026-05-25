"""Tests for OCR-backed page parsing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import fitz

from backend.ingestion.parsers.page_image_parser import PageImageParser
from backend.core.models import ChunkType


def test_page_image_parser_uses_ocr_when_page_has_no_text(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scan.pdf"
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    doc.save(str(pdf_path))
    doc.close()

    ocr_text = (
        "8 Software testing\n\nObjectives\n"
        "To introduce software testing and its role in system development."
    )

    parser = PageImageParser(use_ocr=True, min_text_chars=20)
    with patch(
        "backend.ingestion.parsers.page_image_parser.ocr_image",
        return_value=ocr_text,
    ):
        chunks = parser.parse(pdf_path)

    page_chunks = [c for c in chunks if c.chunk_type == ChunkType.PAGE_IMAGE]
    text_chunks = [c for c in chunks if c.chunk_type == ChunkType.TEXT]

    assert len(page_chunks) == 1
    assert "Objectives" in page_chunks[0].content
    assert page_chunks[0].metadata.get("ocr") is True
    assert len(text_chunks) == 1
    assert text_chunks[0].metadata.get("source") == "ocr"


def test_page_image_parser_skips_ocr_when_disabled(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scan.pdf"
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    doc.save(str(pdf_path))
    doc.close()

    parser = PageImageParser(use_ocr=False)
    with patch(
        "backend.ingestion.parsers.page_image_parser.ocr_image",
    ) as mock_ocr:
        chunks = parser.parse(pdf_path)

    mock_ocr.assert_not_called()
    assert chunks[0].content == "Page 1 image (no extractable text)"
