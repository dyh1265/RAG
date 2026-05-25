"""Prometheus metrics for ingestion throughput and latency."""

from __future__ import annotations

import os

# Must be set before Counter/Histogram construction for Celery prefork workers.
_MP_DIR = os.environ.get("PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus_multiproc")
os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", _MP_DIR)
os.makedirs(_MP_DIR, exist_ok=True)

from prometheus_client import Counter, Histogram, start_http_server  # noqa: E402

INGEST_DOCS = Counter(
    "rag_ingest_documents_total",
    "Documents processed by scalable ingest",
    ["status"],
)
INGEST_CHUNKS = Counter("rag_ingest_chunks_total", "Chunks upserted after embedding")
EMBED_CACHE_HITS = Counter("rag_embed_cache_hits_total", "Embedding cache hits")
EMBED_CACHE_MISSES = Counter("rag_embed_cache_misses_total", "Embedding cache misses")
DEDUP_REMOVED = Counter("rag_dedup_chunks_removed_total", "Near-duplicate chunks removed")
QDRANT_ERRORS = Counter("rag_qdrant_errors_total", "Qdrant operation failures")
EMBED_LATENCY = Histogram(
    "rag_embed_seconds",
    "Time spent in embedding encode calls",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

_server_started = False


def start_metrics_server(port: int | None = None) -> None:
    """
    Start /metrics HTTP server once (Celery prefork-safe via multiproc dir).

    Safe to call from worker_ready; ignores 'address already in use'.
    """
    global _server_started
    if _server_started:
        return
    from prometheus_client import CollectorRegistry, multiprocess

    from shared.config import get_settings

    port = port or get_settings().ingest_metrics_port
    try:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        start_http_server(port, registry=registry)
    except OSError as exc:
        # Another worker process already bound :9100 — metrics still aggregate via multiproc dir.
        if exc.errno not in (98, 48, 10048):  # EADDRINUSE Linux/macOS/Windows
            raise
    _server_started = True


def record_embed_latency(seconds: float) -> None:
    EMBED_LATENCY.observe(seconds)


def record_ingest_success(chunk_count: int, *, skipped: bool = False) -> None:
    INGEST_DOCS.labels(status="skipped" if skipped else "success").inc()
    if not skipped:
        INGEST_CHUNKS.inc(chunk_count)


def record_ingest_failure() -> None:
    INGEST_DOCS.labels(status="error").inc()


def record_cache_stats(hits: int, misses: int) -> None:
    if hits:
        EMBED_CACHE_HITS.inc(hits)
    if misses:
        EMBED_CACHE_MISSES.inc(misses)


def record_dedup_removed(count: int) -> None:
    if count:
        DEDUP_REMOVED.inc(count)
