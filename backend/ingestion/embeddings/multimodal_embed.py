"""Embed helpers for text, CLIP figures, and optional ColPali page images."""

from __future__ import annotations

from backend.core.models import ChunkType, DocumentChunk, EmbeddedChunk
from backend.ingestion.embeddings.colpali_embedder import ColPaliEmbedder
from backend.ingestion.embeddings.image_embedder import ImageEmbedder
from backend.ingestion.embeddings.text_embedder import TextEmbedder

TEXT_CHUNK_TYPES = {ChunkType.TEXT, ChunkType.TABLE, ChunkType.HEADING}
TEXT_OR_PAGE_TYPES = TEXT_CHUNK_TYPES | {ChunkType.PAGE_IMAGE}


def embed_chunks(
    chunks: list[DocumentChunk],
    text_embedder: TextEmbedder,
    image_embedder: ImageEmbedder,
    colpali_embedder: ColPaliEmbedder | None = None,
    *,
    use_colpali: bool = False,
) -> list[EmbeddedChunk]:
    """Route chunks to text, CLIP figure, or ColPali page embedder by type."""
    text_types = TEXT_CHUNK_TYPES if use_colpali else TEXT_OR_PAGE_TYPES
    text_chunks = [c for c in chunks if c.chunk_type in text_types]
    figure_chunks = [c for c in chunks if c.chunk_type == ChunkType.FIGURE]
    page_chunks = [c for c in chunks if c.chunk_type == ChunkType.PAGE_IMAGE] if use_colpali else []

    embedded: list[EmbeddedChunk] = []
    embedded.extend(text_embedder.embed_chunks(text_chunks))
    embedded.extend(image_embedder.embed_figure_chunks(figure_chunks))

    if page_chunks:
        if colpali_embedder is None:
            raise ValueError("use_colpali=True requires a ColPaliEmbedder instance")
        embedded.extend(colpali_embedder.embed_page_chunks(page_chunks))

    return embedded
