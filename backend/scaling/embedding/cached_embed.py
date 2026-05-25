"""Cache-aware embedding wrapper around multimodal embedders."""

from __future__ import annotations

import time
from dataclasses import dataclass

from backend.ingestion.embeddings.colpali_embedder import ColPaliEmbedder
from backend.ingestion.embeddings.image_embedder import ImageEmbedder
from backend.ingestion.embeddings.multimodal_embed import TEXT_CHUNK_TYPES, TEXT_OR_PAGE_TYPES, embed_chunks
from backend.ingestion.embeddings.text_embedder import TextEmbedder
from backend.scaling.embedding.fingerprint import chunk_embed_key
from backend.scaling.embedding.redis_cache import EmbeddingCache
from backend.scaling.monitoring.metrics import record_embed_latency
from backend.core.models import ChunkType, DocumentChunk, EmbeddedChunk


@dataclass
class CachedEmbedStats:
    cache_hits: int = 0
    cache_misses: int = 0


def embed_chunks_cached(
    chunks: list[DocumentChunk],
    text_embedder: TextEmbedder,
    image_embedder: ImageEmbedder,
    colpali_embedder: ColPaliEmbedder | None = None,
    *,
    use_colpali: bool = False,
    cache: EmbeddingCache | None = None,
) -> tuple[list[EmbeddedChunk], CachedEmbedStats]:
    """Like embed_chunks but reads/writes vectors through Redis when cache is available."""
    if cache is None or not cache.available():
        t0 = time.perf_counter()
        embedded = embed_chunks(
            chunks,
            text_embedder,
            image_embedder,
            colpali_embedder,
            use_colpali=use_colpali,
        )
        record_embed_latency(time.perf_counter() - t0)
        return embedded, CachedEmbedStats()

    stats = CachedEmbedStats()
    text_types = TEXT_CHUNK_TYPES if use_colpali else TEXT_OR_PAGE_TYPES
    text_chunks = [c for c in chunks if c.chunk_type in text_types]
    figure_chunks = [c for c in chunks if c.chunk_type == ChunkType.FIGURE]
    page_chunks = [c for c in chunks if c.chunk_type == ChunkType.PAGE_IMAGE] if use_colpali else []

    embedded: list[EmbeddedChunk] = []
    embedded.extend(_embed_text_cached(text_chunks, text_embedder, cache, stats))
    embedded.extend(_embed_figures_cached(figure_chunks, image_embedder, cache, stats))

    if page_chunks:
        if colpali_embedder is None:
            raise ValueError("use_colpali=True requires a ColPaliEmbedder instance")
        t0 = time.perf_counter()
        embedded.extend(colpali_embedder.embed_page_chunks(page_chunks))
        record_embed_latency(time.perf_counter() - t0)
        stats.cache_misses += len(page_chunks)

    return embedded, stats


def _embed_text_cached(
    chunks: list[DocumentChunk],
    embedder: TextEmbedder,
    cache: EmbeddingCache,
    stats: CachedEmbedStats,
) -> list[EmbeddedChunk]:
    if not chunks:
        return []

    results: list[EmbeddedChunk | None] = [None] * len(chunks)
    miss_indices: list[int] = []
    miss_texts: list[str] = []

    for i, chunk in enumerate(chunks):
        key = chunk_embed_key(chunk)
        cached = cache.get_vector(key, embedder.model_name)
        if cached is not None:
            results[i] = EmbeddedChunk(chunk=chunk, vector=cached, model_name=embedder.model_name)
            stats.cache_hits += 1
        else:
            miss_indices.append(i)
            miss_texts.append(chunk.enriched_content)

    if miss_texts:
        t0 = time.perf_counter()
        vectors = embedder.embed_texts(miss_texts)
        record_embed_latency(time.perf_counter() - t0)
        stats.cache_misses += len(miss_texts)
        for idx, vec in zip(miss_indices, vectors):
            chunk = chunks[idx]
            key = chunk_embed_key(chunk)
            cache.set_vector(key, embedder.model_name, vec)
            results[idx] = EmbeddedChunk(chunk=chunk, vector=vec, model_name=embedder.model_name)

    return [r for r in results if r is not None]


def _embed_figures_cached(
    chunks: list[DocumentChunk],
    embedder: ImageEmbedder,
    cache: EmbeddingCache,
    stats: CachedEmbedStats,
) -> list[EmbeddedChunk]:
    if not chunks:
        return []

    results: list[EmbeddedChunk] = []
    miss_chunks: list[DocumentChunk] = []

    for chunk in chunks:
        key = chunk_embed_key(chunk)
        cached = cache.get_vector(key, embedder.model_name)
        if cached is not None:
            results.append(EmbeddedChunk(chunk=chunk, vector=cached, model_name=embedder.model_name))
            stats.cache_hits += 1
        else:
            miss_chunks.append(chunk)

    if miss_chunks:
        t0 = time.perf_counter()
        fresh = embedder.embed_figure_chunks(miss_chunks)
        record_embed_latency(time.perf_counter() - t0)
        stats.cache_misses += len(miss_chunks)
        for ec in fresh:
            key = chunk_embed_key(ec.chunk)
            cache.set_vector(key, embedder.model_name, ec.vector)
            results.append(ec)

    return results
