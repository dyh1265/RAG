"""FastAPI dependencies — pipeline, settings, and session resolution."""

from __future__ import annotations

from fastapi import HTTPException, Request

from backend.api.sessions import verify_token
from backend.core.config import Settings, get_settings
from backend.core.pipeline import RAGPipeline

#: Tenant that owns CLI/eval/server-side ingests and any caller that presents
#: no session token. Keeps non-browser usage working unchanged.
DEFAULT_TENANT = "public"


def get_app_settings() -> Settings:
    return get_settings()


def _extract_token(request: Request) -> str | None:
    """Pull a session token from the Authorization header or ``t`` query param.

    The query param is needed for resources the browser loads directly (e.g. a
    PDF preview ``<iframe src>``), which cannot set request headers.
    """
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
        if token:
            return token
    token = request.query_params.get("t")
    return token.strip() if token else None


def get_tenant_id(request: Request) -> str:
    """Resolve the caller's tenant from their signed session token.

    A missing token maps to :data:`DEFAULT_TENANT` (server-side/CLI flows). A
    token that is present but invalid or expired is rejected, since it can only
    mean a tampered or stale client — never a legitimate anonymous visitor.
    """
    token = _extract_token(request)
    if token is None:
        return DEFAULT_TENANT

    tenant_id = verify_token(token)
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
    return tenant_id


def get_pipeline(request: Request) -> RAGPipeline:
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise RuntimeError("RAG pipeline is not initialised")
    return pipeline
