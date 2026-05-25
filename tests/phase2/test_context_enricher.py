"""Tests for Phase 2 context enrichment."""

from __future__ import annotations

from shared.models import ChunkType, DocumentChunk, DocumentType
from phases.phase_02_long_doc_retrieval.enrichment.context_enricher import enrich_chunks


def test_enrich_chunks_adds_prefix():
    chunk = DocumentChunk(
        doc_id="doc1",
        source_path="report.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.TEXT,
        content="Revenue grew 18%.",
        section_path="Revenue Analysis",
    )
    enriched = enrich_chunks([chunk], doc_title="sample report")
    assert enriched[0].context_prefix is not None
    assert "sample report" in enriched[0].context_prefix
    assert "Revenue Analysis" in enriched[0].context_prefix
    assert "Revenue grew" in enriched[0].enriched_content
