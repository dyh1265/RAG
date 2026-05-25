"""Shared fixtures for Phase 1 unit tests."""

from __future__ import annotations

import pytest

from backend.core.models import ChunkType, DocumentChunk, DocumentType, RetrievalStrategy, RetrievedContext


@pytest.fixture
def sample_pdf_path():
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "data" / "raw" / "sample_report.pdf"
    if not path.exists():
        pytest.skip("sample_report.pdf not found — run scripts/generate_sample_report.py")
    return path


def make_chunk(
    *,
    chunk_id: str = "chunk-1",
    chunk_type: ChunkType = ChunkType.TEXT,
    content: str = "Sample content",
    page_number: int | None = 1,
    doc_id: str = "doc-abc",
) -> DocumentChunk:
    return DocumentChunk(
        id=chunk_id,
        doc_id=doc_id,
        source_path="/data/sample.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=chunk_type,
        content=content,
        page_number=page_number,
    )


def make_context(
    *,
    chunk_id: str = "chunk-1",
    chunk_type: ChunkType = ChunkType.TEXT,
    content: str = "Sample content",
    score: float = 0.9,
    rank: int = 1,
    page_number: int | None = 1,
) -> RetrievedContext:
    return RetrievedContext(
        chunk=make_chunk(
            chunk_id=chunk_id,
            chunk_type=chunk_type,
            content=content,
            page_number=page_number,
        ),
        score=score,
        strategy=RetrievalStrategy.DENSE,
        rank=rank,
    )
