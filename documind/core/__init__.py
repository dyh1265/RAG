"""Core models, config, and pipeline (wraps ``shared/``)."""

from shared.config import Settings, get_settings
from shared.directory_ingest import DirectoryIngestSummary, ingest_directory
from shared.models import (
    ChunkType,
    DocumentChunk,
    DocumentType,
    EmbeddedChunk,
    QueryRequest,
    QueryResponse,
    RetrievedContext,
)
from shared.pdf_paths import collect_pdf_paths, resolve_under_base
from shared.pipeline import IngestResult, PipelineConfig, RAGPipeline

__all__ = [
    "Settings",
    "get_settings",
    "RAGPipeline",
    "PipelineConfig",
    "IngestResult",
    "QueryRequest",
    "QueryResponse",
    "RetrievedContext",
    "DocumentChunk",
    "EmbeddedChunk",
    "ChunkType",
    "DocumentType",
    "collect_pdf_paths",
    "resolve_under_base",
    "ingest_directory",
    "DirectoryIngestSummary",
]
