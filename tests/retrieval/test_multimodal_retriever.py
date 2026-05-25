"""Tests for RRF fusion, query hints, and content deduplication."""

from __future__ import annotations

from unittest.mock import MagicMock


from backend.retrieval.multimodal_retriever import (
    MultiModalRetriever,
    _collection_weights,
    _dedupe_by_content,
    reciprocal_rank_fusion,
)
from backend.ingestion.stores.qdrant_store import COLLECTION_MAP
from backend.core.models import ChunkType, QueryRequest
from tests._factories import make_context


def test_reciprocal_rank_fusion_orders_by_rank_within_list():
    ranked = [
        make_context(chunk_id="a", content="first"),
        make_context(chunk_id="b", content="second"),
    ]

    fused = reciprocal_rank_fusion([ranked], k=60)

    assert len(fused) == 2
    assert fused[0].chunk.id == "a"
    assert fused[1].chunk.id == "b"
    assert fused[0].score > fused[1].score


def test_reciprocal_rank_fusion_merges_disjoint_lists():
    list_a = [make_context(chunk_id="a", content="from text collection")]
    list_b = [make_context(chunk_id="b", content="from figure collection")]

    fused = reciprocal_rank_fusion([list_a, list_b], k=60)

    assert len(fused) == 2
    assert {r.chunk.id for r in fused} == {"a", "b"}


def test_reciprocal_rank_fusion_weight_boosts_collection():
    figure = make_context(chunk_id="fig", chunk_type=ChunkType.FIGURE, content="chart")
    text = make_context(chunk_id="txt", chunk_type=ChunkType.TEXT, content="caption")

    fused = reciprocal_rank_fusion(
        [[text], [figure]],
        k=60,
        weights=[1.0, 2.5],
    )

    assert fused[0].chunk.id == "fig"
    assert fused[0].score > fused[1].score


def test_collection_weights_boost_figure_for_chart_query():
    weights = _collection_weights("What does Figure 3 show about revenue trends?", False)
    assert weights[COLLECTION_MAP[ChunkType.FIGURE]] == 2.5
    assert weights[COLLECTION_MAP[ChunkType.PAGE_IMAGE]] == 0.5


def test_collection_weights_boost_table_for_margin_query():
    weights = _collection_weights("What was Q4 2024 operating margin?", False)
    assert weights[COLLECTION_MAP[ChunkType.TABLE]] == 2.5


def test_dedupe_by_content_prefers_figure_over_text():
    shared = "Figure 3 shows quarterly revenue trends."
    figure = make_context(
        chunk_id="fig",
        chunk_type=ChunkType.FIGURE,
        content=shared,
        score=0.04,
        rank=1,
    )
    text = make_context(
        chunk_id="txt",
        chunk_type=ChunkType.TEXT,
        content=shared,
        score=0.03,
        rank=2,
    )

    deduped = _dedupe_by_content([figure, text], top_k=5)

    assert len(deduped) == 1
    assert deduped[0].chunk.chunk_type == ChunkType.FIGURE


def test_multimodal_retriever_searches_all_collections():
    store = MagicMock()
    store.collection_vector_size.return_value = 2
    store.search.side_effect = lambda vector, collection_name, top_k, filters=None: [
        make_context(
            chunk_id=f"hit-{collection_name}",
            content=f"content from {collection_name}",
            rank=1,
        )
    ]

    text_embedder = MagicMock()
    text_embedder.embed_texts.return_value = [[0.1, 0.2]]
    image_embedder = MagicMock()
    image_embedder.embed_query.return_value = [0.3, 0.4]

    retriever = MultiModalRetriever(store, text_embedder, image_embedder, use_colpali=False)
    results = retriever.retrieve(QueryRequest(query="Figure 3 chart trend", top_k=3))

    assert store.search.call_count == 4
    assert len(results) == 3
    assert text_embedder.embed_texts.called
    assert image_embedder.embed_query.called


def test_resolve_query_vector_falls_back_when_page_chunks_not_colpali():
    import warnings

    from backend.retrieval.multimodal_retriever import _ModalitySearch

    store = MagicMock()
    store.collection_vector_size.return_value = 1024

    text_embedder = MagicMock()
    image_embedder = MagicMock()
    colpali = MagicMock()

    retriever = MultiModalRetriever(
        store,
        text_embedder,
        image_embedder,
        colpali_embedder=colpali,
        use_colpali=True,
    )
    modality = _ModalitySearch("page_chunks", ChunkType.PAGE_IMAGE, "colpali")
    text_vector = [0.1] * 1024
    page_vector = [0.2] * 128

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        vector, source = retriever._resolve_query_vector(
            modality,
            text_vector=text_vector,
            figure_vector=[0.3] * 512,
            page_vector=page_vector,
        )

    assert len(vector) == 1024
    assert source == "text"
    assert any("page_chunks" in str(w.message) for w in caught)


def test_hybrid_text_search_merges_page_chunks_when_not_colpali():
    from tests._factories import make_chunk

    store = MagicMock()
    page_chunk = make_chunk(
        chunk_id="p1",
        chunk_type=ChunkType.PAGE_IMAGE,
        content="Core Practices: TDD, Pair Programming, CI",
    )

    def scroll(collection_name, *, filters=None):
        if collection_name == COLLECTION_MAP[ChunkType.TEXT]:
            return [make_chunk(chunk_id="t1", content="Overview of XP practices")]
        if collection_name == COLLECTION_MAP[ChunkType.PAGE_IMAGE]:
            return [page_chunk]
        return []

    store.scroll_collection.side_effect = scroll

    text_embedder = MagicMock()
    image_embedder = MagicMock()
    retriever = MultiModalRetriever(
        store,
        text_embedder,
        image_embedder,
        use_colpali=False,
        use_hybrid=True,
    )

    captured: dict[str, list] = {}

    class FakeHybrid:
        def __init__(self, corpus, *args, **kwargs):
            captured["corpus"] = corpus

        def retrieve(self, request):
            return [
                make_context(
                    chunk_id=page_chunk.id,
                    chunk_type=ChunkType.PAGE_IMAGE,
                    content=page_chunk.content,
                    rank=1,
                )
            ]

    import backend.retrieval.hybrid_retriever as hybrid_mod

    original = hybrid_mod.HybridRetriever
    hybrid_mod.HybridRetriever = FakeHybrid
    try:
        hits = retriever._hybrid_text_search(
            QueryRequest(
                query="core practices Extreme Programming",
                top_k=3,
                filters={"doc_id": "doc-abc"},
            ),
            fetch_k=9,
        )
    finally:
        hybrid_mod.HybridRetriever = original

    scrolled = [call.args[0] for call in store.scroll_collection.call_args_list]
    assert COLLECTION_MAP[ChunkType.TEXT] in scrolled
    assert COLLECTION_MAP[ChunkType.PAGE_IMAGE] in scrolled
    assert hits is not None
    assert len(captured["corpus"]) == 2
    assert any("Core Practices" in c.content for c in captured["corpus"])
