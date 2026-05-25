"""Integration retrieval-quality eval over golden_set.jsonl."""

from __future__ import annotations

import pytest

from backend.core.models import QueryRequest
from backend.core.pipeline import RAGPipeline
from tests.eval.golden import GoldenCase
from tests.eval.metrics import hit_at_k, latency_p95_ms, mean_metric, mrr, recall_at_k
from tests.eval.thresholds import eval_thresholds

pytestmark = [pytest.mark.integration, pytest.mark.eval]


def _run_retrieval_eval(
    pipeline: RAGPipeline,
    cases: list[GoldenCase],
    *,
    top_k: int,
) -> dict[str, float]:
    recalls: list[float] = []
    hits: list[float] = []
    mrrs: list[float] = []
    retrieve_latencies: list[float] = []

    for case in cases:
        request = QueryRequest(
            query=case.query,
            top_k=top_k,
            filters={"doc_id": case.doc_id},
        )
        response = pipeline.query(request, generate_answer=False)
        contexts = response.retrieved_contexts
        retrieve_latencies.append(response.latency_ms or 0.0)
        recalls.append(recall_at_k(contexts, case.relevant_pages, k=5))
        hits.append(hit_at_k(contexts, case.relevant_pages, k=5))
        mrrs.append(mrr(contexts, case.relevant_pages))

    # Drop first query (cold embedder / cache warmup).
    warmed_latencies = retrieve_latencies[1:] if len(retrieve_latencies) > 1 else retrieve_latencies

    return {
        "recall_at_5": mean_metric(recalls),
        "hit_at_5": mean_metric(hits),
        "mrr": mean_metric(mrrs),
        "retrieve_p95_ms": latency_p95_ms(warmed_latencies),
    }


def test_retrieval_meets_thresholds(
    eval_pipeline: RAGPipeline,
    golden_cases: list[GoldenCase],
    eval_top_k: int,
) -> None:
    scores = _run_retrieval_eval(eval_pipeline, golden_cases, top_k=eval_top_k)
    limits = eval_thresholds()

    assert scores["recall_at_5"] >= limits["recall_at_5"], (
        f"recall@5 {scores['recall_at_5']:.3f} < {limits['recall_at_5']}"
    )
    assert scores["hit_at_5"] >= limits["hit_at_5"], (
        f"hit@5 {scores['hit_at_5']:.3f} < {limits['hit_at_5']}"
    )
    assert scores["mrr"] >= limits["mrr"], f"mrr {scores['mrr']:.3f} < {limits['mrr']}"
    assert scores["retrieve_p95_ms"] <= limits["retrieval_latency_p95_ms"], (
        f"retrieve p95 {scores['retrieve_p95_ms']:.0f}ms > {limits['retrieval_latency_p95_ms']}ms "
        "(after warmup; raise EVAL_RETRIEVAL_LATENCY_P95_MS on slow CPUs)"
    )
