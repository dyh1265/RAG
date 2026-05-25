"""Tests for MinHash deduplication."""

from __future__ import annotations

from backend.scaling.embedding.dedup import deduplicate_chunks
from backend.core.models import ChunkType, DocumentChunk, DocumentType


def _chunk(content: str, chunk_id: str) -> DocumentChunk:
    return DocumentChunk(
        id=chunk_id,
        doc_id="d",
        source_path="/x.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.TEXT,
        content=content,
    )


def test_deduplicate_removes_near_duplicate():
    base = "Agile methods release new versions every two or three weeks to customers in practice."
    dup = base + " Extra words at end."
    kept, removed = deduplicate_chunks([_chunk(base, "a"), _chunk(dup, "b")], threshold=0.7)
    assert removed == 1
    assert len(kept) == 1


def test_deduplicate_keeps_distinct():
    a = _chunk("Revenue grew eighteen percent year over year in fiscal twenty twenty four.", "a")
    b = _chunk("Security engineering focuses on browsers middleware and database systems.", "b")
    kept, removed = deduplicate_chunks([a, b])
    assert removed == 0
    assert len(kept) == 2
