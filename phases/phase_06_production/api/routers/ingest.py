"""Document ingest endpoint."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from phases.phase_06_production.api.dependencies import get_app_settings, get_pipeline
from phases.phase_06_production.api.rate_limit import limiter, rate_limit
from phases.phase_06_production.api.schemas import DirectoryIngestBody, DirectoryIngestOut, IngestResponseOut
from phases.phase_06_production.monitoring.metrics import INGEST_REQUESTS
from shared.config import Settings
from shared.directory_ingest import ingest_directory
from shared.pdf_paths import resolve_under_base
from shared.pipeline import RAGPipeline

router = APIRouter()


def _to_ingest_out(result) -> IngestResponseOut:
    return IngestResponseOut(
        doc_id=result.doc_id,
        source_path=result.source_path,
        chunk_count=result.chunk_count,
        chunks_by_type=result.chunks_by_type,
        vectors_by_collection=result.vectors_by_collection,
        errors=result.errors,
        skipped=result.skipped,
    )


@router.post("/directory", response_model=DirectoryIngestOut)
@limiter.limit(rate_limit())
async def ingest_directory_route(
    request: Request,
    body: DirectoryIngestBody,
    pipeline: RAGPipeline = Depends(get_pipeline),
    settings: Settings = Depends(get_app_settings),
) -> DirectoryIngestOut:
    INGEST_REQUESTS.inc()
    base = Path(settings.raw_docs_dir).resolve()
    try:
        directory = resolve_under_base(body.directory, base)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not directory.is_dir():
        raise HTTPException(status_code=404, detail=f"Directory not found: {directory}")

    summary = await asyncio.to_thread(
        ingest_directory,
        pipeline,
        directory,
        recursive=body.recursive,
    )
    return DirectoryIngestOut(
        directory=summary.directory,
        total_files=summary.total_files,
        ingested=summary.ingested,
        skipped=summary.skipped,
        failed=summary.failed,
        documents=[_to_ingest_out(r) for r in summary.results if r.doc_id],
    )


@router.post("", response_model=IngestResponseOut)
@limiter.limit(rate_limit())
async def ingest_upload(
    request: Request,
    file: UploadFile = File(...),
    pipeline: RAGPipeline = Depends(get_pipeline),
    settings: Settings = Depends(get_app_settings),
) -> IngestResponseOut:
    INGEST_REQUESTS.inc()

    upload_dir = Path(settings.raw_docs_dir) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "document.pdf").suffix or ".pdf"
    dest = upload_dir / f"{uuid.uuid4().hex}{suffix}"
    content = await file.read()
    await asyncio.to_thread(dest.write_bytes, content)

    result = await asyncio.to_thread(pipeline.ingest, dest)
    return _to_ingest_out(result)
