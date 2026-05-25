"""Ingest mode selection — full multimodal vs text-only."""

from __future__ import annotations

from enum import Enum

from shared.config import get_settings
from phases.phase_01_multimodal_ingestion.ingestion_pipeline import IngestionPipeline
from phases.phase_01_multimodal_ingestion.parsers.figure_parser import FigureParser
from phases.phase_01_multimodal_ingestion.parsers.page_image_parser import PageImageParser
from phases.phase_01_multimodal_ingestion.parsers.pdf_text_parser import PDFTextParser
from phases.phase_01_multimodal_ingestion.parsers.table_parser import TableParser


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
