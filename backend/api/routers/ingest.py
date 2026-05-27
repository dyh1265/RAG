"""Document ingest endpoint."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from backend.api.dependencies import get_app_settings, get_pipeline
from backend.api.rate_limit import limiter, rate_limit
from backend.api.schemas import DirectoryIngestBody, DirectoryIngestOut, IngestResponseOut
from backend.api.monitoring.metrics import INGEST_REQUESTS
from backend.core.config import Settings
from backend.core.directory_ingest import ingest_directory
from backend.core.pdf_paths import resolve_under_base
from backend.core.pipeline import RAGPipeline

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


async def _save_upload(
    file: UploadFile,
    settings: Settings,
) -> tuple[Path, str]:
    upload_dir = Path(settings.raw_docs_dir) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = file.filename or "document.pdf"
    suffix = Path(filename).suffix or ".pdf"
    dest = upload_dir / f"{uuid.uuid4().hex}{suffix}"
    content = await file.read()
    await asyncio.to_thread(dest.write_bytes, content)
    return dest, filename


@router.post("", response_model=IngestResponseOut)
@limiter.limit(rate_limit())
async def ingest_upload(
    request: Request,
    file: UploadFile = File(...),
    pipeline: RAGPipeline = Depends(get_pipeline),
    settings: Settings = Depends(get_app_settings),
) -> IngestResponseOut:
    INGEST_REQUESTS.inc()
    dest, _ = await _save_upload(file, settings)
    result = await asyncio.to_thread(pipeline.ingest, dest)
    return _to_ingest_out(result)


@router.post("/stream")
@limiter.limit(rate_limit())
async def ingest_stream(
    request: Request,
    file: UploadFile = File(...),
    pipeline: RAGPipeline = Depends(get_pipeline),
    settings: Settings = Depends(get_app_settings),
) -> StreamingResponse:
    """SSE ingest with live progress (stage + message + optional detail)."""
    INGEST_REQUESTS.inc()
    dest, filename = await _save_upload(file, settings)
    file_size = dest.stat().st_size

    async def events():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

        def on_progress(stage: str, message: str, detail: dict[str, Any] | None) -> None:
            payload = {"stage": stage, "message": message}
            if detail:
                payload["detail"] = detail
            loop.call_soon_threadsafe(queue.put_nowait, ("progress", payload))

        def run_ingest() -> None:
            try:
                result = pipeline.ingest(dest, on_progress=on_progress)
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    ("done", _to_ingest_out(result).model_dump(mode="json")),
                )
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))

        yield (
            "event: progress\n"
            f"data: {json.dumps({'stage': 'uploading', 'message': 'PDF saved', 'detail': {'filename': filename, 'bytes': file_size}})}\n\n"
        )

        task = asyncio.create_task(asyncio.to_thread(run_ingest))
        try:
            while True:
                kind, payload = await queue.get()
                if kind == "progress":
                    yield f"event: progress\ndata: {json.dumps(payload)}\n\n"
                elif kind == "done":
                    yield f"event: done\ndata: {json.dumps(payload)}\n\n"
                    break
                elif kind == "error":
                    yield f"event: error\ndata: {json.dumps({'message': payload})}\n\n"
                    break
        finally:
            await task

    return StreamingResponse(events(), media_type="text/event-stream")
