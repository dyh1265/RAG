"""Tests for slide/page-scoped retrieval of YouTube lectures."""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.core.models import ChunkType, QueryRequest
from backend.ingestion.stores.qdrant_store import COLLECTION_MAP
from backend.retrieval.asset_refs import parse_page_reference
from backend.retrieval.multimodal_retriever import MultiModalRetriever
from tests._factories import make_chunk


def test_parse_page_reference():
    assert parse_page_reference("what did the author say about slides on page 7") == 7
    assert parse_page_reference("explain slide 12 please") == 12
    assert parse_page_reference("see pg. 3") == 3
    assert parse_page_reference("slide #4 summary") == 4
    assert parse_page_reference("the first 7 pages are intro") is None
    assert parse_page_reference("what is a backdoor path") is None


def _slide_text(num: int, ts: float, content: str):
    return make_chunk(
        chunk_id=f"slide-text-{num}",
        chunk_type=ChunkType.TEXT,
        content=content,
        page_number=num,
        metadata={"modality": "slide", "slide_number": num, "timestamp": ts},
    )


def _slide_page(num: int, ts: float):
    return make_chunk(
        chunk_id=f"slide-page-{num}",
        chunk_type=ChunkType.PAGE_IMAGE,
        content=f"OCR slide {num}",
        page_number=num,
        metadata={"modality": "slide", "slide_number": num, "timestamp": ts},
    )


def _transcript(cid: str, start: float, end: float, content: str):
    return make_chunk(
        chunk_id=cid,
        chunk_type=ChunkType.TRANSCRIPT,
        content=content,
        page_number=None,
        metadata={"modality": "transcript", "start_time": start, "end_time": end},
    )


def _build_retriever(store: MagicMock) -> MultiModalRetriever:
    store.search.return_value = []
    store.collection_vector_size.return_value = 1024
    text_embedder = MagicMock()
    text_embedder.embed_texts.return_value = [[0.1] * 1024]
    image_embedder = MagicMock()
    image_embedder.embed_query.return_value = [0.1] * 1024
    return MultiModalRetriever(
        store,
        text_embedder,
        image_embedder,
        use_hybrid=False,
        use_parent_expand=False,
    )


def test_page_query_returns_slide_and_windowed_transcript():
    pages = [_slide_page(6, 100.0), _slide_page(7, 200.0), _slide_page(8, 300.0)]
    texts = [
        _slide_text(7, 200.0, "Slide 7: Backdoor criterion"),
        _transcript("t-before", 150.0, 195.0, "talking about slide six"),
        _transcript("t-during", 205.0, 260.0, "now the backdoor criterion blocks paths"),
        _transcript("t-straddle", 290.0, 340.0, "moving on to identification"),
        _transcript("t-after", 360.0, 400.0, "later unrelated content"),
    ]

    store = MagicMock()

    def scroll(collection_name, *, filters=None):
        if collection_name == COLLECTION_MAP[ChunkType.PAGE_IMAGE]:
            return pages
        if collection_name == COLLECTION_MAP[ChunkType.TEXT]:
            return texts
        return []

    store.scroll_collection.side_effect = scroll
    retriever = _build_retriever(store)

    results = retriever.retrieve(
        QueryRequest(
            query="what did the author say on page 7",
            top_k=5,
            filters={"doc_id": "vid-1"},
        )
    )
    ids = [r.chunk.id for r in results]

    assert len(results) == 3
    assert results[0].chunk.id == "slide-text-7"
    assert "t-during" in ids
    assert "t-straddle" in ids
    assert "t-before" not in ids
    assert "t-after" not in ids
    during = next(r for r in results if r.chunk.id == "t-during")
    assert during.chunk.metadata.get("aligned_slide_number") == 7


def test_page_query_on_non_video_doc_returns_no_slide_hits():
    body = make_chunk(chunk_id="body", content="ordinary pdf text", page_number=7)

    store = MagicMock()

    def scroll(collection_name, *, filters=None):
        if collection_name == COLLECTION_MAP[ChunkType.TEXT]:
            return [body]
        return []

    store.scroll_collection.side_effect = scroll
    retriever = _build_retriever(store)

    results = retriever.retrieve(
        QueryRequest(query="page 7", top_k=5, filters={"doc_id": "pdf-1"})
    )
    assert all(r.score != 100.0 for r in results)


def test_last_slide_window_extends_to_end():
    pages = [_slide_page(1, 10.0), _slide_page(2, 50.0)]
    texts = [
        _slide_text(2, 50.0, "Slide 2 content"),
        _transcript("t-final", 120.0, 200.0, "final remarks about the last slide"),
    ]

    store = MagicMock()

    def scroll(collection_name, *, filters=None):
        if collection_name == COLLECTION_MAP[ChunkType.PAGE_IMAGE]:
            return pages
        if collection_name == COLLECTION_MAP[ChunkType.TEXT]:
            return texts
        return []

    store.scroll_collection.side_effect = scroll
    retriever = _build_retriever(store)

    results = retriever.retrieve(
        QueryRequest(query="slide 2", top_k=5, filters={"doc_id": "vid-1"})
    )
    ids = [r.chunk.id for r in results]
    assert "slide-text-2" in ids
    assert "t-final" in ids
