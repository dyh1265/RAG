"""Tests for parent-child retrieve-expand."""

from __future__ import annotations

from backend.retrieval.retrieval.parent_expand import collect_parent_ids, expand_to_parents
from backend.core.models import ChunkType, DocumentChunk, DocumentType, RetrievalStrategy, RetrievedContext
from tests.ingestion.conftest import make_context


def test_collect_parent_ids():
    child = DocumentChunk(
        id="child-1",
        doc_id="d1",
        source_path="x.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.TEXT,
        content="small fragment",
        metadata={"parent_chunk_id": "parent-1"},
    )
    contexts = [
        RetrievedContext(
            chunk=child,
            score=0.9,
            strategy=RetrievalStrategy.HYBRID,
            rank=1,
        )
    ]
    assert collect_parent_ids(contexts) == {"parent-1"}


def test_expand_to_parents_replaces_child_with_parent():
    child_ctx = make_context(
        chunk_id="child-1",
        content="pair programming",
        score=0.95,
        rank=1,
    )
    child_ctx.chunk.metadata["parent_chunk_id"] = "parent-1"

    parent_chunk = DocumentChunk(
        id="parent-1",
        doc_id="d1",
        source_path="x.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.TEXT,
        content="Full agile chapter section about pair programming and efficiency.",
        page_number=85,
    )
    parent_map = {
        "parent-1": RetrievedContext(
            chunk=parent_chunk,
            score=0.0,
            strategy=RetrievalStrategy.DENSE,
            rank=0,
        )
    }

    expanded = expand_to_parents([child_ctx], parent_map)
    assert len(expanded) == 1
    assert expanded[0].chunk.id == "parent-1"
    assert expanded[0].score == 0.95
    assert expanded[0].chunk.page_number == 85
