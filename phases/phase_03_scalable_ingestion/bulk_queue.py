"""Queue scalable ingest tasks on Celery."""

from __future__ import annotations

from shared.config import get_settings


def default_ingest_task_options() -> dict:
    """Task options aligned with production API defaults."""
    settings = get_settings()
    return {
        "text_only": True,
        "hybrid": settings.use_hybrid,
        "recursive_chunk": settings.use_recursive_chunker,
        "semantic_chunk": settings.use_semantic_chunker,
        "use_colpali": settings.use_colpali,
        "skip_unchanged": True,
        "use_cache": True,
        "use_dedup": True,
        "force": False,
    }


def celery_workers_available(timeout: float = 2.0) -> bool:
    try:
        from phases.phase_03_scalable_ingestion.workers.celery_app import app

        inspect = app.control.inspect(timeout=timeout)
        ping = inspect.ping()
        return bool(ping)
    except Exception:
        return False


def queue_document(path: str, *, job_id: str | None = None, options: dict | None = None):
    from phases.phase_03_scalable_ingestion.workers.tasks import ingest_document

    opts = options or default_ingest_task_options()
    return ingest_document.delay(path, opts, job_id)


def queue_documents(paths: list[str], *, job_id: str, options: dict | None = None) -> int:
    for path in paths:
        queue_document(path, job_id=job_id, options=options)
    return len(paths)


def queue_pending_documents(job, *, options: dict | None = None) -> list[str]:
    """Return paths still missing from job.results (not yet recorded)."""
    from phases.phase_03_scalable_ingestion.jobs.bulk_job_store import BulkJobStatus

    if not isinstance(job, BulkJobStatus):
        raise TypeError("job must be BulkJobStatus")
    pending = job.pending_paths()
    if pending:
        queue_documents(pending, job_id=job.job_id, options=options)
    return pending
