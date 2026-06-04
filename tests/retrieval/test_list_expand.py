"""Tests for split bullet-list expansion across pages."""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.core.models import ChunkType, DocumentChunk, DocumentType, RetrievalStrategy, RetrievedContext
from backend.retrieval.list_expand import expand_split_list_items


def _view_chunk(
    chunk_id: str,
    page: int,
    line: str,
) -> DocumentChunk:
    return DocumentChunk(
        id=chunk_id,
        doc_id="doc-1",
        source_path="arch.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.TEXT,
        content=line,
        page_number=page,
    )


def test_expand_split_list_items_adds_next_page_siblings():
    logical = _view_chunk("c1", 1, "- Logical view: Shows key system ideas and components.")
    process = _view_chunk("c2", 1, "- Process view: Shows how the system runs during operation.")
    development = _view_chunk("c3", 2, "- Development view: Shows how the software is divided among developers.")
    physical = _view_chunk("c4", 2, "- Physical view: Shows how the software maps to hardware.")
    intro = DocumentChunk(
        id="intro",
        doc_id="doc-1",
        source_path="arch.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.TEXT,
        content="Because a system is complex, it is described from different viewpoints, such as:",
        page_number=1,
    )

    store = MagicMock()
    store.scroll_collection.return_value = [logical, process, development, physical, intro]

    contexts = [
        RetrievedContext(chunk=logical, score=0.9, strategy=RetrievalStrategy.HYBRID, rank=1),
        RetrievedContext(chunk=process, score=0.8, strategy=RetrievalStrategy.HYBRID, rank=2),
        RetrievedContext(
            chunk=intro,
            score=0.7,
            strategy=RetrievalStrategy.HYBRID,
            rank=3,
        ),
    ]

    expanded = expand_split_list_items(store, "doc-1", contexts, top_k=8)
    contents = {ctx.chunk.content for ctx in expanded}

    assert "- Development view:" in "\n".join(contents)
    assert "- Physical view:" in "\n".join(contents)
    assert len(expanded) >= 4
