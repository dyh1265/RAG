"""Retrieval and answer-quality metrics for RAG evaluation."""

from __future__ import annotations

import math
import re
from statistics import mean

from backend.core.models import RetrievedContext


def _page_numbers(contexts: list[RetrievedContext], *, k: int | None = None) -> list[int | None]:
    sliced = contexts if k is None else contexts[:k]
    return [ctx.chunk.page_number for ctx in sliced]


def _first_relevant_rank(pages: list[int | None], relevant: set[int]) -> int | None:
    for idx, page in enumerate(pages, start=1):
        if page is not None and page in relevant:
            return idx
    return None


def recall_at_k(
    contexts: list[RetrievedContext],
    relevant_pages: list[int],
    k: int,
) -> float:
    """
    Fraction of labelled relevant pages hit in the top-k retrieved chunks.
    """
    relevant = set(relevant_pages)
    if not relevant:
        return 0.0
    hit_pages = {
        page
        for page in _page_numbers(contexts, k=k)
        if page is not None and page in relevant
    }
    return len(hit_pages) / len(relevant)


def hit_at_k(
    contexts: list[RetrievedContext],
    relevant_pages: list[int],
    k: int,
) -> float:
    """1.0 if any relevant page appears in top-k, else 0.0."""
    return 1.0 if recall_at_k(contexts, relevant_pages, k) > 0 else 0.0


def mrr(contexts: list[RetrievedContext], relevant_pages: list[int]) -> float:
    """Mean reciprocal rank of the first relevant chunk (0 if none)."""
    rank = _first_relevant_rank(_page_numbers(contexts), set(relevant_pages))
    return 0.0 if rank is None else 1.0 / rank


def mean_metric(values: list[float]) -> float:
    return mean(values) if values else 0.0


def keyword_coverage(answer: str, key_phrases: list[str]) -> float:
    """
    Fraction of key phrases found in the answer (case-insensitive, whitespace-normalized).
    Used as an offline faithfulness proxy when Ragas is unavailable.
    """
    if not key_phrases:
        return 1.0
    normalized = re.sub(r"\s+", " ", answer.lower())
    hits = sum(1 for phrase in key_phrases if phrase.lower() in normalized)
    return hits / len(key_phrases)


def latency_p95_ms(latencies: list[float]) -> float:
    if not latencies:
        return 0.0
    sorted_ms = sorted(latencies)
    idx = min(len(sorted_ms) - 1, max(0, math.ceil(0.95 * len(sorted_ms)) - 1))
    return sorted_ms[idx]
