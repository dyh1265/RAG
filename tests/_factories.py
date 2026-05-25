"""Plain factories for building test chunks/contexts. Shared across test packages.

Kept as a regular module (not a conftest) because callers import the functions
directly by name (`from tests._factories import make_chunk`).
"""

from __future__ import annotations

from backend.core.models import (
    ChunkType,
    DocumentChunk,
    DocumentType,
    RetrievalStrategy,
    RetrievedContext,
)


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
