"""Ingest mode selection — full multimodal vs text-only."""

from __future__ import annotations

from enum import Enum

from backend.core.config import get_settings
from backend.ingestion.ingestion_pipeline import IngestionPipeline
from backend.ingestion.parsers.figure_parser import FigureParser
from backend.ingestion.parsers.page_image_parser import PageImageParser
from backend.ingestion.parsers.pdf_text_parser import PDFTextParser
from backend.ingestion.parsers.table_parser import TableParser


class IngestMode(str, Enum):
    FULL = "full"
    TEXT_ONLY = "text_only"


def build_ingestion_pipeline(mode: IngestMode) -> IngestionPipeline:
    """Return an IngestionPipeline configured for the requested mode."""
    settings = get_settings()
    text_parsers = [PDFTextParser(), TableParser()]
    if mode == IngestMode.TEXT_ONLY:
        return IngestionPipeline(text_parsers)
    return IngestionPipeline(
        text_parsers
        + [
            FigureParser(use_ocr=settings.use_ocr),
            PageImageParser(use_ocr=settings.use_ocr, ocr_lang=settings.ocr_lang),
        ]
    )
