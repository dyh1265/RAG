"""Tests for shared.pipeline.RAGPipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from shared.models import ChunkType, QueryRequest
from shared.pipeline import PipelineConfig, RAGPipeline
from tests.phase1.conftest import make_chunk, make_context


def test_ingest_parses_embeds_and_upserts():
    chunk = make_chunk(chunk_id="c1", chunk_type=ChunkType.TEXT, content="Revenue grew.")
    store = MagicMock()
    embedded = MagicMock(chunk=chunk, vector=[0.1], model_name="bge-m3")

    pipeline = RAGPipeline(store=store)
    pipeline._ingestion = MagicMock()
    pipeline._ingestion.parse_safe.return_value = ([chunk], [])

    with patch("shared.pipeline.embed_chunks", return_value=[embedded]):
        result = pipeline.ingest("/data/report.pdf")

    store.delete_doc.assert_called_once()
    store.upsert.assert_called_once()
    assert result.chunk_count == 1
    assert result.chunks_by_type["text"] == 1
    assert result.vectors_by_collection["text_chunks"] == 1


def test_query_retrieve_only_skips_llm():
    pipeline = RAGPipeline(store=MagicMock())
    pipeline._retriever = MagicMock()
    pipeline._retriever.retrieve.return_value = [make_context(chunk_id="c1")]

    response = pipeline.query(
        QueryRequest(query="What is revenue?", top_k=3),
        generate_answer=False,
    )

    assert response.answer == ""
    assert len(response.retrieved_contexts) == 1
    pipeline._retriever.retrieve.assert_called_once()


def test_query_generates_answer():
    pipeline = RAGPipeline(PipelineConfig(llm_provider="openai"), store=MagicMock())
    pipeline._retriever = MagicMock()
    pipeline._retriever.retrieve.return_value = [make_context(chunk_id="c1")]

    mock_response = MagicMock()
    mock_response.query = "Q?"
    mock_response.answer = "Revenue rose."
    mock_response.citations = []
    mock_response.retrieved_contexts = pipeline._retriever.retrieve.return_value
    mock_response.model_used = "openai:gpt-4o-mini"
    mock_response.latency_ms = 10.0

    with patch("shared.pipeline.AnswerGenerator") as gen_cls:
        gen_cls.return_value.generate.return_value = mock_response
        response = pipeline.query(QueryRequest(query="Q?"))

    assert response.answer == "Revenue rose."
    gen_cls.return_value.generate.assert_called_once()
