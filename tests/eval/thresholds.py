"""Read evaluation thresholds from application settings."""

from __future__ import annotations

from backend.core.config import Settings, get_settings


def eval_thresholds(settings: Settings | None = None) -> dict[str, float]:
    s = settings or get_settings()
    return {
        "faithfulness": s.eval_faithfulness_threshold,
        "keyword_coverage": s.eval_keyword_coverage_threshold,
        "recall_at_5": s.eval_recall_at_5_threshold,
        "hit_at_5": s.eval_hit_at_5_threshold,
        "mrr": s.eval_mrr_threshold,
        "latency_p95_ms": s.eval_latency_p95_ms,
        "retrieval_latency_p95_ms": s.eval_retrieval_latency_p95_ms,
        "regression_tolerance": s.eval_regression_tolerance,
    }
