"""FastAPI dependencies — pipeline and settings from app.state."""

from __future__ import annotations

from fastapi import Request

from backend.core.config import Settings, get_settings
from backend.core.pipeline import RAGPipeline


def get_app_settings() -> Settings:
    return get_settings()


def get_pipeline(request: Request) -> RAGPipeline:
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise RuntimeError("RAG pipeline is not initialised")
    return pipeline
