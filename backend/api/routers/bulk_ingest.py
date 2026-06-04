"""Bulk folder ingest via Celery + Redis job tracking."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from backend.scaling.bulk_queue import (
    celery_workers_available,
    default_ingest_task_options,
    queue_documents,
    queue_pending_documents,
)
from backend.scaling.jobs.bulk_job_store import BulkJobStore
from backend.api.dependencies import get_app_settings, get_tenant_id
from backend.api.rate_limit import limiter, rate_limit
from backend.api.schemas import (
    BulkIngestJobOut,
    BulkIngestRunOut,
    BulkIngestStartBody,
    BulkIngestStartOut,
    BulkIngestUploadOut,
)
from backend.core.config import Settings

router = APIRouter(prefix="/bulk")


def _job_dir(settings: Settings, job_id: str) -> Path:
    return Path(settings.raw_docs_dir) / "uploads" / "bulk" / job_id


def _require_owned_job(store: BulkJobStore, job_id: str, tenant_id: str):
    """Fetch a job and 404 unless it belongs to the calling tenant.

    Returning 404 (not 403) avoids confirming that someone else's job id exists.
    """
    job = store.get(job_id)
    if job is None or job.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Bulk job not found")
    return job


def _to_job_out(job) -> BulkIngestJobOut:
    return BulkIngestJobOut(
        job_id=job.job_id,
        folder_name=job.folder_name,
        status=job.status,
        total=job.total,
        uploaded=job.uploaded,
        processed=job.processed,
        ingested=job.ingested,
        skipped=job.skipped,
        failed=job.failed,
        current_file=job.current_file,
        message=job.message,
    )


@router.post("/start", response_model=BulkIngestStartOut)
@limiter.limit(rate_limit())
async def bulk_start(
    request: Request,
    body: BulkIngestStartBody,
    settings: Settings = Depends(get_app_settings),
    tenant_id: str = Depends(get_tenant_id),
) -> BulkIngestStartOut:
    if body.total_files < 1:
        raise HTTPException(status_code=400, detail="total_files must be at least 1")
    job_id = uuid.uuid4().hex
    store = BulkJobStore()
    try:
        store.client.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}") from exc
    store.create(
        job_id,
        folder_name=body.folder_name,
        total=body.total_files,
        tenant_id=tenant_id,
    )
    _job_dir(settings, job_id).mkdir(parents=True, exist_ok=True)
    return BulkIngestStartOut(job_id=job_id, total_files=body.total_files)


@router.post("/{job_id}/files", response_model=BulkIngestUploadOut)
@limiter.limit(rate_limit())
async def bulk_upload_file(
    request: Request,
    job_id: str,
    file: UploadFile = File(...),
    settings: Settings = Depends(get_app_settings),
    tenant_id: str = Depends(get_tenant_id),
) -> BulkIngestUploadOut:
    store = BulkJobStore()
    job = _require_owned_job(store, job_id, tenant_id)
    if job.status != "uploading":
        raise HTTPException(status_code=409, detail=f"Job is not accepting uploads (status={job.status})")

    suffix = Path(file.filename or "document.pdf").suffix or ".pdf"
    safe_name = Path(file.filename or "document.pdf").name
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}{suffix}" if suffix == ".pdf" else safe_name

    dest_dir = _job_dir(settings, job_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe_name
    content = await file.read()
    dest.write_bytes(content)

    job = store.add_uploaded_path(job_id, str(dest.resolve()), safe_name)
    return BulkIngestUploadOut(
        job_id=job_id,
        uploaded=job.uploaded,
        total=job.total,
        filename=safe_name,
    )


@router.post("/{job_id}/run", response_model=BulkIngestRunOut)
@limiter.limit(rate_limit())
async def bulk_run(
    request: Request,
    job_id: str,
    settings: Settings = Depends(get_app_settings),
    tenant_id: str = Depends(get_tenant_id),
) -> BulkIngestRunOut:
    store = BulkJobStore()
    job = _require_owned_job(store, job_id, tenant_id)
    if job.status != "uploading":
        raise HTTPException(status_code=409, detail=f"Job cannot be started (status={job.status})")
    if job.uploaded < job.total:
        raise HTTPException(
            status_code=400,
            detail=f"Upload incomplete: {job.uploaded}/{job.total} files received",
        )
    if not celery_workers_available():
        raise HTTPException(
            status_code=503,
            detail="Celery ingest worker not running. Start: docker compose --profile production up -d ingest-worker",
        )

    paths = job.paths
    if not paths:
        dest_dir = _job_dir(settings, job_id)
        paths = [str(p.resolve()) for p in sorted(dest_dir.glob("*.pdf"))]
    if not paths:
        store.mark_error(job_id, "No PDF files uploaded")
        raise HTTPException(status_code=400, detail="No PDF files in job")

    store.mark_queued(job_id)
    options = {**default_ingest_task_options(), "tenant_id": job.tenant_id}
    queued = queue_documents(paths, job_id=job_id, options=options)
    return BulkIngestRunOut(job_id=job_id, queued=queued, status="queued")


@router.post("/{job_id}/resume", response_model=BulkIngestRunOut)
@limiter.limit(rate_limit())
async def bulk_resume(
    request: Request,
    job_id: str,
    tenant_id: str = Depends(get_tenant_id),
) -> BulkIngestRunOut:
    """Re-queue PDFs that were never processed (e.g. after worker restart)."""
    store = BulkJobStore()
    job = _require_owned_job(store, job_id, tenant_id)
    if job.status not in {"queued", "running"}:
        raise HTTPException(status_code=409, detail=f"Job cannot be resumed (status={job.status})")
    pending = job.pending_paths()
    if not pending:
        return BulkIngestRunOut(job_id=job_id, queued=0, status=job.status)
    if not celery_workers_available():
        raise HTTPException(
            status_code=503,
            detail="Celery ingest worker not running. Start: docker compose --profile production up -d ingest-worker",
        )

    store.mark_queued(job_id, message=f"Resuming {len(pending)} remaining file(s)")
    options = {**default_ingest_task_options(), "tenant_id": job.tenant_id}
    queued = queue_pending_documents(job, options=options)
    return BulkIngestRunOut(job_id=job_id, queued=len(queued), status="queued")


@router.get("/{job_id}", response_model=BulkIngestJobOut)
@limiter.limit(rate_limit())
async def bulk_job_status(
    request: Request,
    job_id: str,
    tenant_id: str = Depends(get_tenant_id),
) -> BulkIngestJobOut:
    job = _require_owned_job(BulkJobStore(), job_id, tenant_id)
    return _to_job_out(job)
