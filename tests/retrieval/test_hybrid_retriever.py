"""Tests for HybridRetriever BM25 + dense fusion."""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.retrieval.retrieval.hybrid_retriever import HybridRetriever, reciprocal_rank_fusion
from backend.core.models import ChunkType, DocumentChunk, DocumentType, QueryRequest, RetrievalStrategy
from tests.ingestion.conftest import make_context


def test_hybrid_retriever_fuses_sparse_and_dense():
    corpus = [
        DocumentChunk(
            id="a",
            doc_id="d1",
            source_path="x.pdf",
            doc_type=DocumentType.PDF,
            chunk_type=ChunkType.TEXT,
            content="Q4 revenue margin table",
        ),
        DocumentChunk(
            id="b",
            doc_id="d1",
            source_path="x.pdf",
            doc_type=DocumentType.PDF,
            chunk_type=ChunkType.TEXT,
            content="unrelated executive summary text",
        ),
    ]
    embedder = MagicMock()
    embedder.embed_texts.return_value = [[0.1, 0.2]]
    store = MagicMock()
    store.search.return_value = [
        make_context(chunk_id="b", content="unrelated executive summary text", rank=1),
    ]

    retriever = HybridRetriever(corpus, embedder, store, doc_id="d1")
    retriever._bm25 = MagicMock()
    retriever._bm25.get_scores.return_value = [2.0, 0.1]
    results = retriever.retrieve(
        QueryRequest(query="Q4 revenue margin", top_k=1, filters={"doc_id": "d1"})
    )

    assert len(results) == 1
    assert results[0].strategy == RetrievalStrategy.HYBRID
    embedder.embed_texts.assert_called_once()
    store.search.assert_called_once()


def test_reciprocal_rank_fusion_prefers_top_of_both_lists():
    sparse = [make_context(chunk_id="a", content="alpha", rank=1)]
    dense = [make_context(chunk_id="a", content="alpha", rank=1)]
    fused = reciprocal_rank_fusion([sparse, dense], k=60)
    assert fused[0].chunk.id == "a"
    assert fused[0].score > 0


def test_boost_section_chunks_promotes_objectives_page():
    from backend.retrieval.retrieval.hybrid_retriever import _boost_section_chunks

    page = make_context(
        chunk_id="page",
        chunk_type=ChunkType.PAGE_IMAGE,
        content="Software testing 8 Objectives The objective of this chapter is to introduce software testing",
        rank=3,
        score=0.04,
    )
    stub = make_context(
        chunk_id="stub",
        chunk_type=ChunkType.PAGE_IMAGE,
        content="Page 17 image (no extractable text)",
        rank=1,
        score=0.9,
    )
    boosted = _boost_section_chunks("objectives of the chapter", [stub, page])
    assert boosted[0].chunk.id == "page"


def test_boost_section_chunks_promotes_bullet_page():
    from backend.retrieval.retrieval.hybrid_retriever import _boost_section_chunks

    page = make_context(
        chunk_id="page",
        chunk_type=ChunkType.PAGE_IMAGE,
        content="Core Practices:\n- TDD\n- Pair Programming",
        rank=3,
        score=0.04,
    )
    text = make_context(chunk_id="text", content="Overview of XP", rank=1, score=0.05)
    boosted = _boost_section_chunks(
        "What are the core practices of Extreme Programming",
        [text, page],
    )
    assert boosted[0].chunk.id == "page"

