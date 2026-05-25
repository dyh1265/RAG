"""Unit tests for eval metric helpers (no Qdrant / LLM)."""

from __future__ import annotations

from tests.eval.metrics import (
    hit_at_k,
    keyword_coverage,
    latency_p95_ms,
    mean_metric,
    mrr,
    recall_at_k,
)
from tests.ingestion.conftest import make_context


def _contexts(pages: list[int | None]) -> list:
    return [
        make_context(chunk_id=f"c{i}", page_number=page, rank=i + 1)
        for i, page in enumerate(pages)
    ]


def test_recall_at_k_partial_hit():
    contexts = _contexts([99, 2, 3, 1])
    assert recall_at_k(contexts, [1, 3], k=4) == 1.0


def test_recall_at_k_miss():
    contexts = _contexts([99, 98])
    assert recall_at_k(contexts, [1, 2], k=2) == 0.0


def test_hit_at_k():
    contexts = _contexts([99, 2])
    assert hit_at_k(contexts, [2], k=2) == 1.0
    assert hit_at_k(contexts, [1], k=2) == 0.0


def test_mrr_first_rank():
    contexts = _contexts([99, 2, 1])
    assert mrr(contexts, [2]) == 0.5


def test_mrr_no_hit():
    contexts = _contexts([99, 98])
    assert mrr(contexts, [1]) == 0.0


def test_keyword_coverage():
    assert keyword_coverage("Revenue was $191.7M (+18.4% YoY)", ["191.7", "18.4"]) == 1.0
    assert keyword_coverage("Revenue grew strongly", ["191.7"]) == 0.0


def test_mean_metric_and_latency_p95():
    assert mean_metric([0.5, 1.0]) == 0.75
    assert latency_p95_ms([10.0, 20.0, 30.0, 40.0, 500.0]) == 500.0
