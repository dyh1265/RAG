"""Celery application for async document ingestion."""

from __future__ import annotations

import os

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown, worker_ready

from shared.config import get_settings

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
)


@worker_ready.connect
def _start_metrics_on_worker_ready(**_kwargs) -> None:
    """Start Prometheus /metrics once when the Celery worker is ready."""
    from phases.phase_03_scalable_ingestion.monitoring.metrics import start_metrics_server

    start_metrics_server()


@worker_process_init.connect
def _preload_models_on_worker_start(**_kwargs) -> None:
    """Load embedding model once per worker process (CPU ingest is single-threaded)."""
    from phases.phase_03_scalable_ingestion.bulk_queue import default_ingest_task_options
    from phases.phase_03_scalable_ingestion.workers import tasks as ingest_tasks

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
import phases.phase_03_scalable_ingestion.workers.tasks as _tasks  # noqa: E402, F401
