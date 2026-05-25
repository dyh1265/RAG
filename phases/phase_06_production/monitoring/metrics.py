"""Prometheus metrics for the RAG API."""

from __future__ import annotations

from prometheus_client import Counter, Histogram, generate_latest

QUERY_REQUESTS = Counter(
    "rag_api_query_requests_total",
    "Total /query requests",
    ["provider", "retrieve_only"],
)
INGEST_REQUESTS = Counter("rag_api_ingest_requests_total", "Total /ingest requests")
QUERY_LATENCY = Histogram(
    "rag_api_query_latency_seconds",
    "End-to-end query latency",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
)
PII_REDACTIONS = Counter("rag_api_pii_redactions_total", "Texts modified by PII redaction")


def metrics_payload() -> bytes:
    return generate_latest()
