"""Integration tests against sample_report.pdf (skipped if file missing)."""

from __future__ import annotations

import pytest

from phases.phase_01_multimodal_ingestion.ingestion_pipeline import IngestionPipeline
from phases.phase_01_multimodal_ingestion.parsers.figure_parser import FigureParser
from phases.phase_01_multimodal_ingestion.parsers.page_image_parser import PageImageParser
from phases.phase_01_multimodal_ingestion.parsers.pdf_text_parser import PDFTextParser
from phases.phase_01_multimodal_ingestion.parsers.table_parser import TableParser
from shared.models import ChunkType


pytestmark = pytest.mark.integration


def test_sample_report_extracts_all_chunk_types(sample_pdf_path):
    pipeline = IngestionPipeline(
        [PDFTextParser(), TableParser(), FigureParser(), PageImageParser()]
    )
    chunks, errors = pipeline.parse_safe(sample_pdf_path)

    assert errors == []
    types = {c.chunk_type for c in chunks}
    assert ChunkType.TEXT in types
    assert ChunkType.TABLE in types
    assert ChunkType.FIGURE in types
    assert ChunkType.PAGE_IMAGE in types
    assert len(chunks) >= 10


def test_sample_report_table_has_quarter_rows(sample_pdf_path):
    pipeline = IngestionPipeline([TableParser()])
    chunks = pipeline.parse(sample_pdf_path)

    assert len(chunks) == 1
    table = chunks[0]
    assert table.chunk_type == ChunkType.TABLE
    assert "Q4 2024" in table.content
    assert "54.6" in table.content


def test_sample_report_figure_has_image_path(sample_pdf_path):
    pipeline = IngestionPipeline([FigureParser()])
    chunks = pipeline.parse(sample_pdf_path)

    assert len(chunks) >= 1
    figure = next(c for c in chunks if c.chunk_type == ChunkType.FIGURE)
    assert figure.image_path is not None
    assert "Figure 3" in figure.content or "figure" in figure.content.lower()
