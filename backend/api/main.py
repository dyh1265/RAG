"""DocuMind production FastAPI service."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.api.rate_limit import limiter
from backend.api.routers import admin, bulk_ingest, health, ingest, query
from backend.api.monitoring.tracing import setup_tracing
from backend.core.config import get_settings
from backend.core.pipeline import PipelineConfig, RAGPipeline


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    config = PipelineConfig(
        use_colpali=settings.use_colpali,
        use_hybrid=settings.use_hybrid,
        use_recursive_chunker=settings.use_recursive_chunker,
        use_semantic_chunker=settings.use_semantic_chunker,
        use_section_paths=settings.use_section_paths,
        use_context_enrichment=settings.use_context_enrichment,
        use_parent_expand=settings.use_parent_expand,
        use_flashrank=settings.use_flashrank,
        use_taxonomy_validation=settings.use_taxonomy_validation,
        block_forbidden_classifications=settings.taxonomy_block_forbidden,
    )
    app.state.pipeline = RAGPipeline(config)
    app.state.models_ready: bool | None = None
    app.state.models_error: str | None = None
    print(f"[startup] RAG API on {settings.api_host}:{settings.api_port}")

    if settings.api_warmup_models:
        try:
            ms = await asyncio.to_thread(app.state.pipeline.preload_models)
            app.state.models_ready = True
            print(f"[startup] models preloaded in {ms:.0f}ms")
        except Exception as exc:
            app.state.models_ready = False
            app.state.models_error = str(exc)
            print(f"[startup] model preload FAILED: {exc}")

    yield
    print("[shutdown] RAG API shutting down.")


app = FastAPI(
    title="DocuMind API",
    description="Multimodal RAG service: PDF ingest, hybrid retrieval, cited answers.",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

_cors_origins = get_settings().cors_allow_origins_list
# Credentials cannot be combined with wildcard origins per the CORS spec, so we
# only enable them when explicit origins are configured (production case).
_cors_allow_credentials = _cors_origins != ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

setup_tracing(app, get_settings())

app.include_router(health.router, tags=["Health"])
app.include_router(query.router, prefix="/query", tags=["Query"])
app.include_router(ingest.router, prefix="/ingest", tags=["Ingest"])
app.include_router(bulk_ingest.router, prefix="/ingest", tags=["Ingest"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
