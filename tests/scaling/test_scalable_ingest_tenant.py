"""Tests that scalable_ingest passes tenant_id through to the vector store."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# scalable_ingest imports RAGPipeline, which pulls optional ML deps.
pytest.importorskip("torch")

from backend.core.pipeline import IngestResult
from backend.scaling.pipeline.scalable_ingest import ScalableIngestConfig, scalable_ingest


@pytest.fixture
def pipeline_and_pdf(tmp_path):
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 minimal")

    pipeline = MagicMock()
    pipeline.config.use_colpali = False
    pipeline.config.use_section_paths = False
    pipeline.config.use_recursive_chunker = False
    pipeline.config.use_semantic_chunker = False
    pipeline.config.use_context_enrichment = False
    pipeline._retrieval_enrichment_enabled.return_value = False
    pipeline.store = MagicMock()
    return pipeline, pdf


def test_scalable_ingest_passes_tenant_to_upsert_and_delete(pipeline_and_pdf):
    pipeline, pdf = pipeline_and_pdf
    chunk = MagicMock()
    chunk.chunk_type.value = "text"
    chunk.id = "c1"

    embedded = MagicMock()
    embedded.chunk = chunk

    with (
        patch(
            "backend.scaling.pipeline.scalable_ingest.build_ingestion_pipeline"
        ) as build_ingestion,
        patch(
            "backend.scaling.pipeline.scalable_ingest.embed_chunks_cached"
        ) as embed_cached,
        patch("backend.scaling.pipeline.scalable_ingest.EmbeddingCache") as cache_cls,
    ):
        ingestion = MagicMock()
        ingestion.parse_safe.return_value = ([chunk], [])
        build_ingestion.return_value = ingestion

        cache = MagicMock()
        cache.available.return_value = False
        cache_cls.return_value = cache

        embed_cached.return_value = ([embedded], MagicMock(cache_hits=0, cache_misses=1))

        result = scalable_ingest(
            pipeline,
            pdf,
            config=ScalableIngestConfig(skip_unchanged=False, use_cache=False),
            tenant_id="celery-tenant-1",
        )

    assert isinstance(result, IngestResult)
    pipeline.store.delete_doc.assert_called_once()
    assert pipeline.store.delete_doc.call_args.kwargs["tenant_id"] == "celery-tenant-1"
    pipeline.store.upsert.assert_called_once()
    assert pipeline.store.upsert.call_args.kwargs["tenant_id"] == "celery-tenant-1"
