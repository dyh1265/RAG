"""
Unified RAG pipeline — single entry point for ingest and query.

Demo, eval, and API should all call RAGPipeline rather than wiring
ingestion / retrieval / scaling components directly.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from backend.core.config import get_settings
from backend.core.models import QueryRequest, QueryResponse, RetrievedContext
from backend.ingestion.embeddings.colpali_embedder import ColPaliEmbedder
from backend.ingestion.embeddings.image_embedder import ImageEmbedder
from backend.ingestion.embeddings.multimodal_embed import embed_chunks
from backend.ingestion.embeddings.text_embedder import TextEmbedder
from backend.generation.answer_generator import AnswerGenerator
from backend.ingestion.parsers.base_parser import stable_doc_id
from backend.ingestion.stores.qdrant_store import COLLECTION_MAP, QdrantStore, page_index_status
from backend.retrieval.cross_encoder_reranker import CrossEncoderReranker
from backend.retrieval.flashrank_reranker import FlashRankReranker
from backend.retrieval.multimodal_retriever import MultiModalRetriever
from backend.retrieval.preprocessing import (
    RetrievalIngestConfig,
    apply_retrieval_ingest,
    invalidate_retrieval_caches,
)
from backend.scaling.pipeline.ingest_modes import IngestMode, build_ingestion_pipeline


@dataclass
class PipelineConfig:
    use_rerank: bool = False
    use_flashrank: bool = False
    use_colpali: bool = False
    llm_provider: str = "ollama"
    use_hybrid: bool = False
    use_recursive_chunker: bool = False
    use_semantic_chunker: bool = False
    use_section_paths: bool = True
    use_context_enrichment: bool = True
    use_parent_expand: bool = True
    use_taxonomy_validation: bool = True
    block_forbidden_classifications: bool = False
    text_only: bool = False


@dataclass
class IngestResult:
    doc_id: str
    source_path: str
    chunk_count: int
    chunks_by_type: dict[str, int] = field(default_factory=dict)
    vectors_by_collection: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    skipped: bool = False
    cache_hits: int = 0
    dedup_removed: int = 0


class RAGPipeline:
    """
    Multimodal RAG pipeline: parse → enrich → embed → store → retrieve → answer.

    Usage
    -----
    pipeline = RAGPipeline()
    pipeline.ingest("data/raw/report.pdf")
    response = pipeline.query(QueryRequest(query="What was Q4 revenue?"))
    """

    def __init__(
        self,
        config: PipelineConfig | None = None,
        store: QdrantStore | None = None,
    ) -> None:
        settings = get_settings()
        self.config = config or PipelineConfig(
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
        self._store = store
        self._text_embedder: TextEmbedder | None = None
        self._image_embedder: ImageEmbedder | None = None
        self._colpali_embedder: ColPaliEmbedder | None = None
        self._reranker: CrossEncoderReranker | None = None
        self._flashrank_reranker: FlashRankReranker | None = None
        self._retriever: MultiModalRetriever | None = None
        if self.config.text_only:
            self._ingestion = build_ingestion_pipeline(IngestMode.TEXT_ONLY)
        else:
            self._ingestion = build_ingestion_pipeline(IngestMode.FULL)

    @property
    def store(self) -> QdrantStore:
        if self._store is None:
            self._store = QdrantStore()
        return self._store

    @property
    def text_embedder(self) -> TextEmbedder:
        if self._text_embedder is None:
            self._text_embedder = TextEmbedder()
        return self._text_embedder

    @property
    def image_embedder(self) -> ImageEmbedder:
        if self._image_embedder is None:
            self._image_embedder = ImageEmbedder()
        return self._image_embedder

    @property
    def colpali_embedder(self) -> ColPaliEmbedder:
        if self._colpali_embedder is None:
            self._colpali_embedder = ColPaliEmbedder()
        return self._colpali_embedder

    @property
    def retriever(self) -> MultiModalRetriever:
        if self._retriever is None:
            reranker = None
            if self.config.use_flashrank:
                if self._flashrank_reranker is None:
                    self._flashrank_reranker = FlashRankReranker()
                reranker = self._flashrank_reranker
            elif self.config.use_rerank:
                if self._reranker is None:
                    self._reranker = CrossEncoderReranker()
                reranker = self._reranker
            colpali = self.colpali_embedder if self.config.use_colpali else None
            self._retriever = MultiModalRetriever(
                self.store,
                self.text_embedder,
                self.image_embedder,
                reranker=reranker,
                colpali_embedder=colpali,
                use_colpali=self.config.use_colpali,
                use_hybrid=self.config.use_hybrid,
                use_parent_expand=self.config.use_parent_expand,
            )
        return self._retriever

    def preload_models(self) -> float:
        """Load embedding models into memory; returns elapsed milliseconds."""
        t0 = time.perf_counter()
        _ = self.text_embedder.model
        self.image_embedder._ensure_loaded()
        if self.config.use_colpali:
            self.colpali_embedder._ensure_loaded()
        if self.config.use_rerank:
            if self._reranker is None:
                self._reranker = CrossEncoderReranker()
            self._reranker._ensure_loaded()
        if self.config.use_flashrank:
            if self._flashrank_reranker is None:
                self._flashrank_reranker = FlashRankReranker()
            self._flashrank_reranker._ensure_loaded()
        return (time.perf_counter() - t0) * 1000

    def page_index_warning(self) -> str | None:
        """Warn when page_chunks in Qdrant does not match ColPali query mode."""
        if not self.config.use_colpali:
            return None
        return page_index_status(self.store, use_colpali=True)

    def _retrieval_enrichment_enabled(self) -> bool:
        return (
            self.config.use_section_paths
            or self.config.use_recursive_chunker
            or self.config.use_semantic_chunker
            or self.config.use_context_enrichment
        )

    def ingest(self, path: str | Path) -> IngestResult:
        """Parse a document, embed chunks, and upsert into Qdrant."""
        pdf_path = Path(path)
        chunks, errors = self._ingestion.parse_safe(pdf_path)

        if self._retrieval_enrichment_enabled():
            chunks = apply_retrieval_ingest(
                chunks,
                pdf_path,
                RetrievalIngestConfig(
                    use_section_paths=self.config.use_section_paths,
                    use_recursive_chunker=self.config.use_recursive_chunker,
                    use_semantic_chunker=self.config.use_semantic_chunker,
                    use_context_enrichment=self.config.use_context_enrichment,
                ),
            )

        chunks_by_type: dict[str, int] = {}
        for chunk in chunks:
            key = chunk.chunk_type.value
            chunks_by_type[key] = chunks_by_type.get(key, 0) + 1

        if not chunks:
            return IngestResult(
                doc_id=stable_doc_id(pdf_path),
                source_path=str(pdf_path),
                chunk_count=0,
                chunks_by_type=chunks_by_type,
                errors=[str(errors[0])] if errors else ["No chunks extracted"],
            )

        try:
            from backend.api.guardrails.pii import redact_chunk_contents

            redact_chunk_contents(chunks)
        except ImportError:
            pass

        doc_id = stable_doc_id(pdf_path)
        self.store.delete_doc(doc_id)
        invalidate_retrieval_caches(doc_id)
        embedded = embed_chunks(
            chunks,
            self.text_embedder,
            self.image_embedder,
            self.colpali_embedder if self.config.use_colpali else None,
            use_colpali=self.config.use_colpali,
        )
        self.store.upsert(embedded)

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
        )

    def retrieve(self, request: QueryRequest) -> list[RetrievedContext]:
        """Retrieve relevant chunks without LLM generation."""
        return self.retriever.retrieve(request)

    def query(
        self,
        request: QueryRequest,
        *,
        generate_answer: bool = True,
        provider: str | None = None,
    ) -> QueryResponse:
        """Retrieve contexts and optionally generate a grounded answer."""
        t0 = time.perf_counter()
        contexts = self.retrieve(request)
        retrieve_ms = (time.perf_counter() - t0) * 1000

        if not generate_answer:
            response = QueryResponse(
                query=request.query,
                answer="",
                retrieved_contexts=contexts,
                latency_ms=retrieve_ms,
                session_id=request.session_id,
            )
            if self.config.use_taxonomy_validation:
                from backend.taxonomy.hooks import apply_conformity_check

                response = apply_conformity_check(
                    response,
                    block_forbidden=self.config.block_forbidden_classifications,
                )
            return response

        generator = AnswerGenerator(provider=provider or self.config.llm_provider)
        response = generator.generate(
            request.query,
            contexts,
            latency_ms=retrieve_ms,
        )

        if self.config.use_taxonomy_validation:
            from backend.taxonomy.hooks import apply_conformity_check

            response = apply_conformity_check(
                response,
                block_forbidden=self.config.block_forbidden_classifications,
            )

        return response
