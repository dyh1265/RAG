"""Celery tasks for scalable ingestion."""

from __future__ import annotations

from pathlib import Path

from phases.phase_03_scalable_ingestion.pipeline.ingest_modes import IngestMode
from phases.phase_03_scalable_ingestion.pipeline.scalable_ingest import (
    ScalableIngestConfig,
    build_pipeline_from_flags,
    preload_pipeline,
    scalable_ingest,
)
from phases.phase_03_scalable_ingestion.workers.celery_app import app

_pipeline = None


def _get_pipeline(options: dict | None):
    global _pipeline
    opts = options or {}
    if _pipeline is None:
        _pipeline = build_pipeline_from_flags(
            hybrid=opts.get("hybrid", False),
            recursive_chunk=opts.get("recursive_chunk", False),
            semantic_chunk=opts.get("semantic_chunk", False),
            use_colpali=opts.get("use_colpali", False),
        )
        preload_pipeline(_pipeline)
    return _pipeline


@app.task(bind=True, name="ingest_document", max_retries=3, default_retry_delay=30)
def ingest_document(self, path: str, options: dict | None = None, job_id: str | None = None) -> dict:
    """Ingest one PDF path via the scalable pipeline."""
    opts = options or {}
    pdf_path = Path(path)
    if not pdf_path.exists():
        result = {"path": path, "status": "error", "error": "file not found", "chunk_count": 0, "errors": ["file not found"]}
        if job_id:
            from phases.phase_03_scalable_ingestion.jobs.bulk_job_store import BulkJobStore

            BulkJobStore().record_task_result(job_id, result)
        return result

    if job_id:
        from phases.phase_03_scalable_ingestion.jobs.bulk_job_store import BulkJobStore

        store = BulkJobStore()
        job = store.get(job_id)
        if job and job.status == "queued":
            store.mark_running(job_id)

    pipeline = _get_pipeline(opts)
    mode = IngestMode.TEXT_ONLY if opts.get("text_only") else IngestMode.FULL
    cfg = ScalableIngestConfig(
        mode=mode,
        skip_unchanged=opts.get("skip_unchanged", True),
        use_cache=opts.get("use_cache", True),
        use_dedup=opts.get("use_dedup", True),
        force=opts.get("force", False),
    )

    try:
        result = scalable_ingest(pipeline, pdf_path, config=cfg)
    except Exception as exc:
        raise self.retry(exc=exc) from exc

    payload = {
        "path": path,
        "status": "skipped" if result.skipped else "success",
        "doc_id": result.doc_id,
        "chunk_count": result.chunk_count,
        "cache_hits": result.cache_hits,
        "dedup_removed": result.dedup_removed,
        "errors": result.errors,
    }
    if job_id:
        from phases.phase_03_scalable_ingestion.jobs.bulk_job_store import BulkJobStore

        BulkJobStore().record_task_result(job_id, payload)
    return payload
