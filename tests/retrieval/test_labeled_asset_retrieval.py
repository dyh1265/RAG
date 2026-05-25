"""Tests for label-aware table/figure retrieval."""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.core.models import ChunkType, QueryRequest
from backend.ingestion.stores.qdrant_store import COLLECTION_MAP
from backend.retrieval.multimodal_retriever import MultiModalRetriever
from tests._factories import make_chunk


def test_figure_query_prepends_caption_chunk():
    fig = make_chunk(
        chunk_id="fig-2",
        chunk_type=ChunkType.FIGURE,
        content="Figure 2. Maximum length of each rank of the UMQ.",
        page_number=179,
    )
    text = make_chunk(
        chunk_id="body",
        content="Some unrelated paragraph about GPUs and message passing on many pages.",
        page_number=179,
    )

    store = MagicMock()

    def scroll(collection_name, *, filters=None):
        if collection_name == COLLECTION_MAP[ChunkType.FIGURE]:
            return [fig]
        if collection_name == COLLECTION_MAP[ChunkType.TEXT]:
            return [text]
        return []

    store.scroll_collection.side_effect = scroll
    store.search.return_value = []
    store.collection_vector_size.return_value = 1024

    text_embedder = MagicMock()
    text_embedder.embed_texts.return_value = [[0.1] * 1024]
    image_embedder = MagicMock()
    image_embedder.embed_query.return_value = [0.1] * 1024

    retriever = MultiModalRetriever(
        store,
        text_embedder,
        image_embedder,
        use_hybrid=False,
    )
    results = retriever.retrieve(
        QueryRequest(
            query="figure 2",
            top_k=3,
            filters={"doc_id": "doc-abc"},
        )
    )
    assert results
    assert results[0].chunk.id == "fig-2"
    assert "Figure 2" in results[0].chunk.content


def test_table_query_uses_page_anchor_from_body_text():
    table = make_chunk(
        chunk_id="tbl-i",
        chunk_type=ChunkType.TABLE,
        content="Rank | UMQ len\n0 | 12\n1 | 8",
        page_number=5,
        doc_id="doc-abc",
    )
    anchor = make_chunk(
        chunk_id="cite",
        content="Table I summarizes the queue lengths on page five.",
        page_number=5,
        doc_id="doc-abc",
    )

    store = MagicMock()

    def scroll(collection_name, *, filters=None):
        if collection_name == COLLECTION_MAP[ChunkType.TABLE]:
            return [table]
        if collection_name == COLLECTION_MAP[ChunkType.TEXT]:
            return [anchor]
        return []

    store.scroll_collection.side_effect = scroll
    store.search.return_value = []
    store.collection_vector_size.return_value = 1024

    text_embedder = MagicMock()
    text_embedder.embed_texts.return_value = [[0.1] * 1024]
    image_embedder = MagicMock()
    image_embedder.embed_query.return_value = [0.1] * 1024

    retriever = MultiModalRetriever(
        store,
        text_embedder,
        image_embedder,
        use_hybrid=False,
    )
    results = retriever.retrieve(
        QueryRequest(
            query="table 1",
            top_k=3,
            filters={"doc_id": "doc-abc"},
        )
    )
    assert results
    assert results[0].chunk.chunk_type == ChunkType.TABLE
    assert "Rank" in results[0].chunk.content


def test_algorithm_query_prepends_title_and_pseudocode():
    title = make_chunk(
        chunk_id="alg-title",
        content="Algorithm 2: Algorithm to reduce a column-vector to a single match.",
        page_number=12,
    )
    body = make_chunk(
        chunk_id="alg-body",
        content="1: int32 mask = 0xFFFFFFFF\n2: if thread_id < warp_size then\n5: int32 bidders = __ballot(vote)",
        page_number=12,
    )
    noise = make_chunk(
        chunk_id="other-page",
        content="Unrelated introduction on page 1.",
        page_number=1,
    )

    store = MagicMock()

    def scroll(collection_name, *, filters=None):
        if collection_name == COLLECTION_MAP[ChunkType.TEXT]:
            return [noise, title, body]
        return []

    store.scroll_collection.side_effect = scroll
    store.search.return_value = []
    store.collection_vector_size.return_value = 1024

    text_embedder = MagicMock()
    text_embedder.embed_texts.return_value = [[0.1] * 1024]
    image_embedder = MagicMock()
    image_embedder.embed_query.return_value = [0.1] * 1024

    retriever = MultiModalRetriever(
        store,
        text_embedder,
        image_embedder,
        use_hybrid=False,
    )
    results = retriever.retrieve(
        QueryRequest(
            query="Algorithm 2",
            top_k=5,
            filters={"doc_id": "doc-abc"},
        )
    )
    ids = [r.chunk.id for r in results]
    assert "alg-title" in ids
    assert "alg-body" in ids
    assert results[0].chunk.id == "alg-title"
    assert "__ballot" in next(r.chunk.content for r in results if r.chunk.id == "alg-body")
