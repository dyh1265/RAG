"""Contextual prefix enrichment before embedding (Phase 2)."""

from __future__ import annotations

from pathlib import Path

from shared.models import DocumentChunk


def enrich_chunks(
    chunks: list[DocumentChunk],
    *,
    doc_title: str | None = None,
) -> list[DocumentChunk]:
    """Set context_prefix from document title and section_path."""
    enriched: list[DocumentChunk] = []
    for chunk in chunks:
        parts: list[str] = []
        if doc_title:
            parts.append(f"Document: {doc_title}")
        if chunk.section_path:
            parts.append(f"Section: {chunk.section_path}")
        if not parts:
            enriched.append(chunk)
            continue
        enriched.append(
            chunk.model_copy(update={"context_prefix": "\n".join(parts)})
        )
    return enriched


def doc_title_from_path(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip()
