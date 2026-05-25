"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from backend.api.monitoring.metrics import metrics_payload
from backend.core.config import get_settings

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> JSONResponse:
    checks: dict[str, str] = {}
    all_ok = True

    try:
        from qdrant_client import QdrantClient

        settings = get_settings()
        client = QdrantClient(url=settings.qdrant_url, timeout=2)
        client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as exc:
        checks["qdrant"] = f"error: {exc}"
        all_ok = False

    try:
        import redis as redis_lib

        settings = get_settings()
        r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        all_ok = False

    status_code = 200 if all_ok else 503
    return JSONResponse(
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
        status_code=status_code,
    )


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=metrics_payload(), media_type="text/plain; version=0.0.4")
