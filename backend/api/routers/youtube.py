"""YouTube lecture ingest endpoint (SSE progress)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.api.dependencies import get_app_settings, get_pipeline, get_tenant_id
from backend.api.monitoring.metrics import INGEST_REQUESTS
from backend.api.rate_limit import limiter, rate_limit
from backend.api.routers.ingest import _to_ingest_out
from backend.api.schemas import YouTubeIngestBody, YouTubeIngestResponse
from backend.core.config import Settings
from backend.core.pipeline import RAGPipeline
from backend.video.youtube_ingestor import YouTubeIngestor

router = APIRouter()


def _to_youtube_out(result) -> YouTubeIngestResponse:
    base = _to_ingest_out(result.ingest)
    return YouTubeIngestResponse(
        **base.model_dump(),
        video_id=result.video_id,
        title=result.title,
        slides_pdf_path=result.slides_pdf_path,
        warnings=result.warnings,
    )


@router.post("/youtube/stream")
@limiter.limit(rate_limit())
async def ingest_youtube_stream(
    request: Request,
    body: YouTubeIngestBody,
    pipeline: RAGPipeline = Depends(get_pipeline),
    settings: Settings = Depends(get_app_settings),
    tenant_id: str = Depends(get_tenant_id),
) -> StreamingResponse:
    """SSE ingest for a YouTube lecture URL (transcript → index_chunks)."""
    if not settings.youtube_ingest_enabled:
        raise HTTPException(status_code=503, detail="YouTube ingest is disabled")

    INGEST_REQUESTS.inc()
    ingestor = YouTubeIngestor(pipeline, settings)

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
                result = ingestor.ingest(
                    body.url,
                    tenant_id=tenant_id,
                    include_transcript=body.include_transcript,
                    include_slides=body.include_slides,
                    sample_every_seconds=body.sample_every_seconds,
                    on_progress=on_progress,
                )
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    ("done", _to_youtube_out(result).model_dump(mode="json")),
                )
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))

        yield (
            "event: progress\n"
            f"data: {json.dumps({'stage': 'validating', 'message': 'YouTube URL accepted'})}\n\n"
        )

        task = asyncio.create_task(asyncio.to_thread(run_ingest))
        try:
            while True:
                try:
                    kind, payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
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
