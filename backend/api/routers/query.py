"""Query endpoints — JSON and SSE streaming."""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.api.dependencies import get_pipeline
from backend.api.rate_limit import limiter, rate_limit
from backend.api.schemas import QueryBody, QueryResponseOut
from backend.api.guardrails.pii import PIIRedactor
from backend.api.monitoring.metrics import PII_REDACTIONS, QUERY_LATENCY, QUERY_REQUESTS
from backend.core.models import QueryRequest
from backend.core.pipeline import RAGPipeline

router = APIRouter()


def _run_query(
    pipeline: RAGPipeline,
    body: QueryBody,
    *,
    block_forbidden: bool | None,
) -> tuple[QueryResponseOut, bool]:
    redactor = PIIRedactor()
    query_text, query_redacted = redactor.redact(body.query)
    if query_redacted:
        PII_REDACTIONS.inc()

    filters = {"doc_id": body.doc_id} if body.doc_id else {}
    request = QueryRequest(query=query_text, top_k=body.top_k, filters=filters)

    if block_forbidden is not None:
        pipeline.config.block_forbidden_classifications = block_forbidden

    response = pipeline.query(
        request,
        generate_answer=not body.retrieve_only,
        provider=body.provider,
    )
    response, response_redacted = redactor.redact_response(response)
    if response_redacted:
        PII_REDACTIONS.inc()
    return (
        QueryResponseOut.from_pipeline(response, pii_redacted=query_redacted or response_redacted),
        query_redacted or response_redacted,
    )


@router.post("", response_model=QueryResponseOut)
@limiter.limit(rate_limit())
async def query_json(
    request: Request,
    body: QueryBody,
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> QueryResponseOut:
    QUERY_REQUESTS.labels(provider=body.provider, retrieve_only=str(body.retrieve_only)).inc()
    t0 = time.perf_counter()
    try:
        out, _ = await asyncio.to_thread(
            _run_query,
            pipeline,
            body,
            block_forbidden=body.block_forbidden,
        )
        return out
    except ValueError as exc:
        msg = str(exc)
        if "torch.load" in msg or "upgrade torch" in msg:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Embedding models failed to load (PyTorch too old for this "
                    "transformers release). Rebuild Docker with torch>=2.6 "
                    "(GPU: use cu124 wheels)."
                ),
            ) from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    finally:
        QUERY_LATENCY.observe(time.perf_counter() - t0)


@router.post("/stream")
@limiter.limit(rate_limit())
async def query_stream(
    request: Request,
    body: QueryBody,
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> StreamingResponse:
    QUERY_REQUESTS.labels(provider=body.provider, retrieve_only=str(body.retrieve_only)).inc()

    async def events():
        yield "event: status\ndata: retrieving\n\n"
        t0 = time.perf_counter()
        out, redacted = await asyncio.to_thread(
            _run_query,
            pipeline,
            body,
            block_forbidden=body.block_forbidden,
        )
        QUERY_LATENCY.observe(time.perf_counter() - t0)
        payload = out.model_dump(mode="json")
        payload["pii_redacted"] = redacted
        yield f"event: answer\ndata: {json.dumps(payload)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
