"""Tests for RAGPipeline.index_chunks — indexing prebuilt DocumentChunks.

These cover the source-agnostic core that lets non-PDF sources (e.g. a YouTube
transcript) reuse the full embed/store pipeline without a file parser.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.core.models import ChunkType, DocumentChunk, DocumentType
from backend.core.pipeline import PipelineConfig, RAGPipeline


def _ingest_only_config() -> PipelineConfig:
    """Minimal config that skips PDF-touching enrichment in unit tests."""
    return PipelineConfig(
        use_section_paths=False,
        use_recursive_chunker=False,
        use_semantic_chunker=False,
        use_context_enrichment=False,
        use_parent_expand=False,
        use_taxonomy_validation=False,
    )


def _video_chunk(content: str = "The speaker explains treatment heterogeneity.") -> DocumentChunk:
    return DocumentChunk(
        id="t1",
        doc_id="youtube_abc123",
        source_path="youtube:abc123",
        doc_type=DocumentType.VIDEO,
        chunk_type=ChunkType.TRANSCRIPT,
        content=content,
        metadata={
            "source_kind": "youtube",
            "modality": "transcript",
            "video_id": "abc123",
            "start_time": 492.0,
            "end_time": 535.0,
        },
    )


def test_index_chunks_indexes_prebuilt_chunks_without_parsing():
    chunk = _video_chunk()
    store = MagicMock()
    embedded = MagicMock(chunk=chunk, vector=[0.1], model_name="bge-m3")

    pipeline = RAGPipeline(_ingest_only_config(), store=store)
    # No parser should be touched when indexing prebuilt chunks.
    pipeline._ingestion = MagicMock()

    with patch("backend.core.pipeline.embed_chunks", return_value=[embedded]) as embed:
        result = pipeline.index_chunks(
            [chunk],
            doc_id="youtube_abc123",
            source_path="youtube:abc123",
        )

    pipeline._ingestion.parse_safe.assert_not_called()
    embed.assert_called_once()
    store.delete_doc.assert_called_once_with("youtube_abc123", tenant_id="public")
    store.upsert.assert_called_once()

    assert result.doc_id == "youtube_abc123"
    assert result.source_path == "youtube:abc123"
    assert result.chunk_count == 1
    assert result.chunks_by_type["transcript"] == 1
    # Transcript chunks map to the existing text collection.
    assert result.vectors_by_collection["text_chunks"] == 1
    assert result.errors == []


def test_index_chunks_emits_progress_stages():
    chunk = _video_chunk()
    store = MagicMock()
    embedded = MagicMock(chunk=chunk, vector=[0.1], model_name="bge-m3")
    stages: list[str] = []

    pipeline = RAGPipeline(_ingest_only_config(), store=store)

    def on_progress(stage: str, _message: str, _detail: dict | None) -> None:
        stages.append(stage)

    with patch("backend.core.pipeline.embed_chunks", return_value=[embedded]):
        pipeline.index_chunks(
            [chunk],
            doc_id="youtube_abc123",
            source_path="youtube:abc123",
            on_progress=on_progress,
        )

    assert "embedding" in stages
    assert "indexing" in stages


def test_index_chunks_empty_returns_no_chunks():
    store = MagicMock()
    pipeline = RAGPipeline(_ingest_only_config(), store=store)

    with patch("backend.core.pipeline.embed_chunks") as embed:
        result = pipeline.index_chunks(
            [],
            doc_id="youtube_abc123",
            source_path="youtube:abc123",
        )

    embed.assert_not_called()
    store.upsert.assert_not_called()
    assert result.chunk_count == 0
    assert result.errors == ["No chunks extracted"]


def test_index_chunks_clears_only_within_tenant():
    """Re-ingest must scope vector deletion to the caller's tenant.

    YouTube doc_ids are deterministic from the video id, so two tenants ingesting
    the same video share a doc_id; an unscoped delete would wipe the other tenant.
    """
    chunk = _video_chunk()
    store = MagicMock()
    embedded = MagicMock(chunk=chunk, vector=[0.1], model_name="bge-m3")

    pipeline = RAGPipeline(_ingest_only_config(), store=store)

    with patch("backend.core.pipeline.embed_chunks", return_value=[embedded]):
        pipeline.index_chunks(
            [chunk],
            doc_id="youtube_abc123",
            source_path="youtube:abc123",
            tenant_id="tenant-A",
        )

    store.delete_doc.assert_called_once_with("youtube_abc123", tenant_id="tenant-A")


def test_index_chunks_respects_clear_existing_false():
    chunk = _video_chunk()
    store = MagicMock()
    embedded = MagicMock(chunk=chunk, vector=[0.1], model_name="bge-m3")

    pipeline = RAGPipeline(_ingest_only_config(), store=store)

    with patch("backend.core.pipeline.embed_chunks", return_value=[embedded]):
        pipeline.index_chunks(
            [chunk],
            doc_id="youtube_abc123",
            source_path="youtube:abc123",
            clear_existing=False,
        )

    store.delete_doc.assert_not_called()
    store.upsert.assert_called_once()


def test_ingest_delegates_to_index_chunks_and_keeps_parser_errors():
    chunk = _video_chunk(content="Revenue grew.")
    store = MagicMock()
    embedded = MagicMock(chunk=chunk, vector=[0.1], model_name="bge-m3")

    pipeline = RAGPipeline(_ingest_only_config(), store=store)
    pipeline._ingestion = MagicMock()
    pipeline._ingestion.parse_safe.return_value = ([chunk], [ValueError("bad page 3")])

    with patch("backend.core.pipeline.embed_chunks", return_value=[embedded]):
        result = pipeline.ingest("/data/report.pdf")

    store.upsert.assert_called_once()
    assert result.chunk_count == 1
    # Parser errors surfaced by parse_safe are still attached to the result.
    assert any("bad page 3" in e for e in result.errors)
