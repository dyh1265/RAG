"""
Tests for shared/models.py — verifies the core data contracts are sound.
Run: pytest tests/test_models.py
"""

from __future__ import annotations

from backend.core.models import (
    ChunkType,
    DocumentChunk,
    DocumentType,
    EvalSample,
    QueryRequest,
    QueryResponse,
    RetrievalStrategy,
)


def test_document_chunk_defaults():
    chunk = DocumentChunk(
        doc_id="doc_1",
        source_path="/data/test.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.TEXT,
        content="Hello world",
    )
    assert chunk.id is not None
    assert chunk.enriched_content == "Hello world"
    assert chunk.context_prefix is None


def test_enriched_content_with_prefix():
    chunk = DocumentChunk(
        doc_id="doc_1",
        source_path="/data/test.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.TEXT,
        content="Revenue rose 15%.",
        context_prefix="This chunk is from Section 2.1: Financial Highlights of the 2023 Annual Report.",
    )
    enriched = chunk.enriched_content
    assert enriched.startswith("This chunk is from Section")
    assert "Revenue rose 15%." in enriched


def test_query_request_defaults():
    req = QueryRequest(query="What is the revenue?")
    assert req.top_k == 5
    assert req.strategy == RetrievalStrategy.HYBRID


def test_query_response_serialisation():
    response = QueryResponse(
        query="What is the revenue?",
        answer="Revenue was $10B.",
        model_used="gpt-4o",
        latency_ms=450.0,
    )
    data = response.model_dump()
    assert data["answer"] == "Revenue was $10B."
    assert data["citations"] == []


def test_eval_sample_roundtrip():
    sample = EvalSample(
        question="What caused the revenue increase?",
        ground_truth_answer="Strong cloud segment performance.",
        tags=["financial", "revenue"],
    )
    assert sample.id is not None
    restored = EvalSample(**sample.model_dump())
    assert restored.question == sample.question
