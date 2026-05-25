"""Fixtures for RAG quality evaluation (Qdrant + embeddings required)."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from backend.core.config import get_settings
from backend.core.pipeline import PipelineConfig, RAGPipeline
from tests.eval.golden import GoldenCase, load_golden_cases

pytestmark = [pytest.mark.integration, pytest.mark.eval]

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PDF = ROOT / "data" / "raw" / "sample_report.pdf"


def qdrant_available() -> bool:
    settings = get_settings()
    try:
        resp = httpx.get(f"{settings.qdrant_url.rstrip('/')}/healthz", timeout=3.0)
        return resp.status_code == 200
    except (httpx.HTTPError, OSError):
        return False


@pytest.fixture(scope="session")
def golden_cases() -> list[GoldenCase]:
    return load_golden_cases()


@pytest.fixture(scope="session")
def eval_pipeline() -> RAGPipeline:
    if not SAMPLE_PDF.exists():
        pytest.skip("sample_report.pdf missing — run scripts/generate_sample_report.py")
    if not qdrant_available():
        pytest.skip("Qdrant not reachable — start docker compose qdrant service")

    settings = get_settings()
    pipeline = RAGPipeline(
        PipelineConfig(
            use_hybrid=settings.use_hybrid,
            use_recursive_chunker=settings.use_recursive_chunker,
            use_semantic_chunker=settings.use_semantic_chunker,
            use_section_paths=settings.use_section_paths,
            use_context_enrichment=settings.use_context_enrichment,
            use_parent_expand=settings.use_parent_expand,
            use_flashrank=settings.use_flashrank,
            use_colpali=settings.use_colpali,
            use_taxonomy_validation=False,
            llm_provider="openai" if settings.openai_api_key else "ollama",
        ),
    )
    result = pipeline.ingest(SAMPLE_PDF)
    if result.chunk_count == 0:
        pytest.skip(f"Ingest produced no chunks: {result.errors}")
    return pipeline


@pytest.fixture
def eval_top_k() -> int:
    return int(os.getenv("EVAL_TOP_K", "10"))
