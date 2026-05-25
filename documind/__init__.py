"""
DocuMind — unified public API for the Advanced RAG project.

Import from here instead of individual phase_* packages::

    from documind import RAGPipeline, DocuMind, get_settings
    from documind.ingestion import PDFTextParser, QdrantStore
    from documind.production import app

Legacy ``phase_*`` and ``shared`` imports continue to work unchanged.
"""

from capstone.pipeline import DocuMind, DocuMindConfig
from phases._legacy import install_legacy_imports
from shared.config import Settings, get_settings
from shared.models import (
    ChunkType,
    DocumentChunk,
    EmbeddedChunk,
    QueryRequest,
    QueryResponse,
    RetrievedContext,
)
from shared.pipeline import IngestResult, PipelineConfig, RAGPipeline

install_legacy_imports()

__all__ = [
    "DocuMind",
    "DocuMindConfig",
    "RAGPipeline",
    "PipelineConfig",
    "IngestResult",
    "Settings",
    "get_settings",
    "QueryRequest",
    "QueryResponse",
    "RetrievedContext",
    "DocumentChunk",
    "EmbeddedChunk",
    "ChunkType",
]

__version__ = "0.1.0"
