"""Celery application for async document ingestion."""

from __future__ import annotations

import os

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown, worker_ready

from backend.core.config import get_settings

settings = get_settings()
broker = settings.celery_broker_url or settings.redis_url

app = Celery("rag_ingest", broker=broker, backend=broker)
app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=1,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Model preload in worker_process_init takes ~25s on a cold CPU container
    # (BGE-M3 + CLIP). Billiard's default 4s "alive ack" timeout SIGKILLs the
    # child before it finishes, sending the pool into a respawn loop after any
    # crash. Give the child enough headroom to actually come up.
    worker_proc_alive_timeout=120.0,
)


@worker_ready.connect
def _start_metrics_on_worker_ready(**_kwargs) -> None:
    """Start Prometheus /metrics once when the Celery worker is ready."""
    from backend.scaling.monitoring.metrics import start_metrics_server

    start_metrics_server()


@worker_process_init.connect
def _preload_models_on_worker_start(**_kwargs) -> None:
    """Load embedding model once per worker process (CPU ingest is single-threaded)."""
    from backend.scaling.bulk_queue import default_ingest_task_options
    from backend.scaling.workers import tasks as ingest_tasks

    opts = default_ingest_task_options()
    ingest_tasks._get_pipeline(opts)
    print("[ingest-worker] embedding models preloaded")


@worker_process_shutdown.connect
def _cleanup_multiproc_metrics(**_kwargs) -> None:
    """Mark fork worker metrics dead so Prometheus multiproc collector stays accurate."""
    if not os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        return
    try:
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(os.getpid())
    except Exception:
        pass


# Register tasks
import backend.scaling.workers.tasks as _tasks  # noqa: E402, F401
