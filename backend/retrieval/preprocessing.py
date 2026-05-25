"""Ingest post-processing: section paths, optional resplit, contextual enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.core.config import get_settings
from backend.core.models import ChunkType, DocumentChunk
from backend.retrieval.chunking.recursive_chunker import RecursiveChunker
from backend.retrieval.chunking.semantic_chunker import SemanticChunker
from backend.retrieval.enrichment.context_enricher import doc_title_from_path, enrich_chunks
from backend.retrieval.enrichment.section_paths import apply_section_paths
from backend.retrieval.hybrid_retriever import invalidate_bm25_cache


@dataclass
class RetrievalIngestConfig:
    use_section_paths: bool = True
    use_recursive_chunker: bool = False
    use_semantic_chunker: bool = False
    use_context_enrichment: bool = True


def apply_retrieval_ingest(
    chunks: list[DocumentChunk],
    path: Path,
    config: RetrievalIngestConfig | None = None,
) -> list[DocumentChunk]:
    """Run section-path tagging, optional resplit, and contextual enrichment."""
    cfg = config or RetrievalIngestConfig()
    result = list(chunks)

    if cfg.use_section_paths:
        result = apply_section_paths(result, path)

    if cfg.use_semantic_chunker:
        result = _semantic_split_text(result)
    elif cfg.use_recursive_chunker:
        result = _recursive_split_text(result)

    if cfg.use_context_enrichment:
        result = enrich_chunks(result, doc_title=doc_title_from_path(path))

    return result


def _split_large_text(
    chunks: list[DocumentChunk],
    chunker,
) -> list[DocumentChunk]:
    settings = get_settings()
    threshold = settings.max_chunk_size

    text_to_split = [
        c for c in chunks if c.chunk_type == ChunkType.TEXT and len(c.content) > threshold
    ]
    if not text_to_split:
        return chunks

    split_ids = {c.id for c in text_to_split}
    kept = [c for c in chunks if c.id not in split_ids]
    return kept + chunker.chunk(text_to_split)


def _semantic_split_text(chunks: list[DocumentChunk]) -> list[DocumentChunk]:
    return _split_large_text(chunks, SemanticChunker())


def _recursive_split_text(chunks: list[DocumentChunk]) -> list[DocumentChunk]:
    return _split_large_text(chunks, RecursiveChunker())


def invalidate_retrieval_caches(doc_id: str) -> None:
    """Clear retrieval query-time caches (e.g. BM25) after re-ingest."""
    invalidate_bm25_cache(doc_id)
