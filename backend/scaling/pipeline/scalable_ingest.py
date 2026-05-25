"""Scalable ingest — skip unchanged docs, Redis cache, dedup, metrics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.ingestion.parsers.base_parser import stable_doc_id
from backend.ingestion.stores.qdrant_store import COLLECTION_MAP
from backend.retrieval.ingest import Phase2IngestConfig, apply_phase2_ingest, invalidate_phase2_caches
from backend.scaling.embedding.cached_embed import embed_chunks_cached
from backend.scaling.embedding.dedup import deduplicate_chunks
from backend.scaling.embedding.fingerprint import chunk_embed_key, doc_fingerprint
from backend.scaling.embedding.redis_cache import EmbeddingCache
from backend.scaling.monitoring.metrics import (
    QDRANT_ERRORS,
    record_cache_stats,
    record_dedup_removed,
    record_ingest_failure,
    record_ingest_success,
)
from backend.scaling.pipeline.ingest_modes import IngestMode, build_ingestion_pipeline
from backend.core.pipeline import IngestResult, PipelineConfig, RAGPipeline


@dataclass
class ScalableIngestConfig:
    mode: IngestMode = IngestMode.FULL
    skip_unchanged: bool = True
    use_cache: bool = True
    use_dedup: bool = True
    force: bool = False


def scalable_ingest(
    pipeline: RAGPipeline,
    path: str | Path,
    *,
    config: ScalableIngestConfig | None = None,
) -> IngestResult:
    """
    Parse, optionally dedup, cache-aware embed, and upsert into Qdrant.

    Skips re-ingest when the document fingerprint is unchanged (Redis meta).
    """
    cfg = config or ScalableIngestConfig()
    pdf_path = Path(path)
    doc_id = stable_doc_id(pdf_path)
    fingerprint = doc_fingerprint(pdf_path)

    cache = EmbeddingCache() if cfg.use_cache else None
    if cache and not cache.available():
        cache = None

    if cfg.skip_unchanged and not cfg.force and cache is not None:
        meta = cache.get_doc_meta(doc_id)
        if meta and meta.get("fingerprint") == fingerprint:
            record_ingest_success(0, skipped=True)
            return IngestResult(
                doc_id=doc_id,
                source_path=str(pdf_path),
                chunk_count=0,
                skipped=True,
            )

    ingestion = build_ingestion_pipeline(cfg.mode)
    chunks, errors = ingestion.parse_safe(pdf_path)

    if pipeline._phase2_enabled():
        chunks = apply_phase2_ingest(
            chunks,
            pdf_path,
            Phase2IngestConfig(
                use_section_paths=pipeline.config.use_section_paths,
                use_recursive_chunker=pipeline.config.use_recursive_chunker,
                use_semantic_chunker=pipeline.config.use_semantic_chunker,
                use_context_enrichment=pipeline.config.use_context_enrichment,
            ),
        )

    dedup_removed = 0
    if cfg.use_dedup and chunks:
        chunks, dedup_removed = deduplicate_chunks(chunks)
        record_dedup_removed(dedup_removed)

    chunks_by_type: dict[str, int] = {}
    for chunk in chunks:
        key = chunk.chunk_type.value
        chunks_by_type[key] = chunks_by_type.get(key, 0) + 1

    if not chunks:
        record_ingest_failure()
        return IngestResult(
            doc_id=doc_id,
            source_path=str(pdf_path),
            chunk_count=0,
            chunks_by_type=chunks_by_type,
            errors=[str(errors[0])] if errors else ["No chunks extracted"],
            dedup_removed=dedup_removed,
        )

    try:
        pipeline.store.delete_doc(doc_id)
        invalidate_phase2_caches(doc_id)
        embedded, embed_stats = embed_chunks_cached(
            chunks,
            pipeline.text_embedder,
            pipeline.image_embedder,
            pipeline.colpali_embedder if pipeline.config.use_colpali else None,
            use_colpali=pipeline.config.use_colpali,
            cache=cache,
        )
        pipeline.store.upsert(embedded)
    except Exception:
        QDRANT_ERRORS.inc()
        record_ingest_failure()
        raise

    record_cache_stats(embed_stats.cache_hits, embed_stats.cache_misses)
    record_ingest_success(len(chunks))

    if cache is not None:
        chunk_keys = {c.id: chunk_embed_key(c) for c in chunks}
        cache.set_doc_meta(doc_id, fingerprint, chunk_keys)
        cache.mark_ingest_done(str(pdf_path))

    vectors_by_collection: dict[str, int] = {}
    for ec in embedded:
        col = COLLECTION_MAP.get(ec.chunk.chunk_type, "text_chunks")
        vectors_by_collection[col] = vectors_by_collection.get(col, 0) + 1

    return IngestResult(
        doc_id=doc_id,
        source_path=str(pdf_path),
        chunk_count=len(chunks),
        chunks_by_type=chunks_by_type,
        vectors_by_collection=vectors_by_collection,
        errors=[str(e) for e in errors],
        cache_hits=embed_stats.cache_hits,
        dedup_removed=dedup_removed,
    )


def build_pipeline_from_flags(
    *,
    hybrid: bool = False,
    recursive_chunk: bool = False,
    semantic_chunk: bool = False,
    use_colpali: bool = False,
    provider: str = "openai",
) -> RAGPipeline:
    """Construct RAGPipeline with Phase 2 + optional ColPali flags."""
    from backend.core.config import get_settings

    settings = get_settings()
    return RAGPipeline(
        PipelineConfig(
            use_colpali=use_colpali or settings.use_colpali,
            use_hybrid=hybrid or settings.use_hybrid,
            use_recursive_chunker=recursive_chunk or settings.use_recursive_chunker,
            use_semantic_chunker=semantic_chunk or settings.use_semantic_chunker,
            use_section_paths=settings.use_section_paths,
            use_context_enrichment=settings.use_context_enrichment,
            use_parent_expand=settings.use_parent_expand,
            llm_provider=provider,
        )
    )


def preload_pipeline(pipeline: RAGPipeline) -> float:
    """Preload models; returns elapsed ms."""
    return pipeline.preload_models()
