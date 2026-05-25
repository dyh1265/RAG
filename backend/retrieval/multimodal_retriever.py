"""
Multimodal retriever: per-collection dense search fused with weighted RRF.

Each Qdrant collection is searched with the embedder matched to its modality
(bge-m3 for text/table/page, CLIP for figures). Results are merged with
Reciprocal Rank Fusion so scores from different embedding spaces are comparable.

Light query hints boost the relevant collection (figure/chart → figure_chunks,
table/margin → table_chunks).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Literal

from backend.core.models import ChunkType, QueryRequest, RetrievalStrategy, RetrievedContext
from backend.ingestion.embeddings.colpali_embedder import ColPaliEmbedder
from backend.ingestion.embeddings.image_embedder import ImageEmbedder
from backend.ingestion.embeddings.text_embedder import TextEmbedder
from backend.ingestion.stores.qdrant_store import COLLECTION_MAP, QdrantStore
from backend.retrieval.chunk_filters import (
    is_substantive_content,
    prefer_substantive_contexts,
)
from backend.retrieval.cross_encoder_reranker import CrossEncoderReranker
from backend.retrieval.parent_expand import collect_parent_ids, expand_to_parents

FIGURE_HINTS = ("figure", "chart", "graph", "diagram", "plot", "visual", "trend")
TABLE_HINTS = ("table", "margin", "quarter", "row", "column", "operating")

# When caption text duplicates across chunk types, prefer the specialised type.
_TYPE_PRIORITY = {
    ChunkType.FIGURE: 4,
    ChunkType.TABLE: 3,
    ChunkType.TEXT: 2,
    ChunkType.HEADING: 2,
    ChunkType.PAGE_IMAGE: 1,
}


@dataclass(frozen=True)
class _ModalitySearch:
    collection: str
    chunk_type: ChunkType
    vector_source: Literal["text", "clip", "colpali"] = "text"
    base_weight: float = 1.0


def _modalities(use_colpali: bool) -> tuple[_ModalitySearch, ...]:
    page_source: Literal["text", "colpali"] = "colpali" if use_colpali else "text"
    return (
        _ModalitySearch(COLLECTION_MAP[ChunkType.TEXT], ChunkType.TEXT, "text"),
        _ModalitySearch(COLLECTION_MAP[ChunkType.TABLE], ChunkType.TABLE, "text"),
        _ModalitySearch(COLLECTION_MAP[ChunkType.FIGURE], ChunkType.FIGURE, "clip"),
        _ModalitySearch(
            COLLECTION_MAP[ChunkType.PAGE_IMAGE],
            ChunkType.PAGE_IMAGE,
            page_source,
            base_weight=0.75,
        ),
    )


def reciprocal_rank_fusion(
    result_lists: list[list[RetrievedContext]],
    k: int = 60,
    weights: list[float] | None = None,
) -> list[RetrievedContext]:
    """Fuse ranked lists with optional per-list weights."""
    list_weights = weights or [1.0] * len(result_lists)
    scores: dict[str, float] = {}
    chunk_map: dict[str, RetrievedContext] = {}

    for list_weight, result_list in zip(list_weights, result_lists):
        for rank, ctx in enumerate(result_list, start=1):
            chunk_id = ctx.chunk.id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + list_weight / (k + rank)
            chunk_map[chunk_id] = ctx

    sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    fused: list[RetrievedContext] = []
    for new_rank, chunk_id in enumerate(sorted_ids, start=1):
        ctx = chunk_map[chunk_id]
        fused.append(
            RetrievedContext(
                chunk=ctx.chunk,
                score=scores[chunk_id],
                strategy=RetrievalStrategy.HYBRID,
                rank=new_rank,
            )
        )
    return fused


def _collection_weights(query: str, use_colpali: bool) -> dict[str, float]:
    """Boost collections that match obvious query intent."""
    q = query.lower()
    weights = {m.collection: m.base_weight for m in _modalities(use_colpali)}
    if any(h in q for h in FIGURE_HINTS):
        weights[COLLECTION_MAP[ChunkType.FIGURE]] = 2.5
        weights[COLLECTION_MAP[ChunkType.PAGE_IMAGE]] = 0.5
    if any(h in q for h in TABLE_HINTS):
        weights[COLLECTION_MAP[ChunkType.TABLE]] = 2.5
    return weights


def _chunk_type_value(chunk_type) -> str:
    return chunk_type.value if hasattr(chunk_type, "value") else str(chunk_type)


def _type_priority(ctx: RetrievedContext) -> int:
    chunk_type = ctx.chunk.chunk_type
    if isinstance(chunk_type, str):
        try:
            chunk_type = ChunkType(chunk_type)
        except ValueError:
            return 0
    return _TYPE_PRIORITY.get(chunk_type, 0)


def _dedupe_by_content(results: list[RetrievedContext], top_k: int) -> list[RetrievedContext]:
    """Drop duplicate caption text; keep figure/table over text/page_image."""
    kept: list[RetrievedContext] = []
    content_best: dict[str, RetrievedContext] = {}

    for ctx in results:
        key = ctx.chunk.content.strip()
        if not key:
            kept.append(ctx)
            continue
        existing = content_best.get(key)
        if existing is None or _type_priority(ctx) > _type_priority(existing):
            content_best[key] = ctx

    merged = kept + list(content_best.values())
    merged.sort(key=lambda r: r.score, reverse=True)

    final: list[RetrievedContext] = []
    for idx, ctx in enumerate(merged[:top_k], start=1):
        final.append(
            RetrievedContext(
                chunk=ctx.chunk,
                score=ctx.score,
                strategy=ctx.strategy,
                rank=idx,
            )
        )
    return final


class MultiModalRetriever:
    """
    Search each Qdrant collection with the right embedder, fuse with weighted RRF.

    Usage
    -----
    retriever = MultiModalRetriever(store, text_embedder, image_embedder)
    results = retriever.retrieve(QueryRequest(query="...", top_k=5))
    """

    def __init__(
        self,
        store: QdrantStore,
        text_embedder: TextEmbedder,
        image_embedder: ImageEmbedder,
        rrf_k: int = 60,
        reranker: CrossEncoderReranker | None = None,
        colpali_embedder: ColPaliEmbedder | None = None,
        use_colpali: bool = False,
        use_hybrid: bool = False,
        use_parent_expand: bool = True,
    ) -> None:
        self.store = store
        self.text_embedder = text_embedder
        self.image_embedder = image_embedder
        self.colpali_embedder = colpali_embedder
        self.use_colpali = use_colpali
        self.use_hybrid = use_hybrid
        self.use_parent_expand = use_parent_expand
        self.rrf_k = rrf_k
        self.reranker = reranker

    def _hybrid_text_search(
        self,
        request: QueryRequest,
        fetch_k: int,
    ) -> list[RetrievedContext] | None:
        doc_id = (request.filters or {}).get("doc_id")
        if not self.use_hybrid or not doc_id:
            return None
        corpus = self.store.scroll_collection(
            COLLECTION_MAP[ChunkType.TEXT],
            filters={"doc_id": doc_id},
        )
        include_page_corpus = not self.use_colpali
        if include_page_corpus:
            page_corpus = self.store.scroll_collection(
                COLLECTION_MAP[ChunkType.PAGE_IMAGE],
                filters={"doc_id": doc_id},
            )
            page_corpus = [
                chunk for chunk in page_corpus if is_substantive_content(chunk.content)
            ]
            corpus = corpus + page_corpus
        if not corpus:
            return None
        from backend.retrieval.hybrid_retriever import HybridRetriever

        hybrid = HybridRetriever(
            corpus,
            self.text_embedder,
            self.store,
            doc_id=str(doc_id),
        )
        hybrid_request = QueryRequest(
            query=request.query,
            top_k=fetch_k,
            filters=request.filters,
        )
        return hybrid.retrieve(hybrid_request)

    def _expand_parent_contexts(
        self,
        contexts: list[RetrievedContext],
    ) -> list[RetrievedContext]:
        if not self.use_parent_expand:
            return contexts

        parent_ids = collect_parent_ids(contexts)
        if not parent_ids:
            return contexts

        parents = self.store.get_chunks_by_ids(
            COLLECTION_MAP[ChunkType.TEXT],
            parent_ids,
        )
        parent_map = {
            parent.id: RetrievedContext(
                chunk=parent,
                score=0.0,
                strategy=RetrievalStrategy.DENSE,
                rank=0,
            )
            for parent in parents
        }
        expanded = expand_to_parents(contexts, parent_map)
        for rank, ctx in enumerate(expanded, start=1):
            ctx.rank = rank
        return expanded

    def _resolve_query_vector(
        self,
        modality: _ModalitySearch,
        *,
        text_vector: list[float],
        figure_vector: list[float],
        page_vector: list[float] | None,
    ) -> tuple[list[float], Literal["text", "clip", "colpali"]]:
        """Pick a query vector whose dimension matches the collection."""
        if modality.vector_source == "clip":
            candidates: list[tuple[Literal["text", "clip", "colpali"], list[float] | None]] = [
                ("clip", figure_vector),
            ]
        elif modality.vector_source == "colpali":
            candidates = [("colpali", page_vector), ("text", text_vector)]
        else:
            candidates = [("text", text_vector)]
            if page_vector is not None:
                candidates.append(("colpali", page_vector))

        col_size = self.store.collection_vector_size(modality.collection)
        if col_size is None:
            source, vector = candidates[0]
            if vector is None:
                raise ValueError(
                    f"No query vector available for collection '{modality.collection}'"
                )
            return vector, source

        for source, vector in candidates:
            if vector is not None and len(vector) == col_size:
                if source != modality.vector_source:
                    warnings.warn(
                        f"'{modality.collection}' is indexed at {col_size}-dim ({source}) "
                        f"but query mode expects {modality.vector_source}. "
                        "Re-ingest without --skip-ingest after toggling ColPali.",
                        stacklevel=2,
                    )
                return vector, source

        dims = ", ".join(
            f"{source}={len(vec)}"
            for source, vec in candidates
            if vec is not None
        )
        raise ValueError(
            f"Cannot query '{modality.collection}' (stored dim {col_size}). "
            f"Available query vectors: {dims}. "
            "Re-ingest without --skip-ingest after toggling ColPali."
        )

    def retrieve(self, request: QueryRequest) -> list[RetrievedContext]:
        fetch_k = max(request.top_k * 3, request.top_k)
        col_weights = _collection_weights(request.query, self.use_colpali)

        text_vector = self.text_embedder.embed_texts([request.query])[0]
        figure_vector = self.image_embedder.embed_query(request.query)
        page_vector = None
        if self.use_colpali:
            if self.colpali_embedder is None:
                raise ValueError("use_colpali=True requires a ColPaliEmbedder instance")
            page_vector = self.colpali_embedder.embed_query(request.query)

        result_lists: list[list[RetrievedContext]] = []
        list_weights: list[float] = []
        doc_scoped = bool((request.filters or {}).get("doc_id"))
        q_lower = request.query.lower()
        hybrid_handled_pages = False

        for modality in _modalities(self.use_colpali):
            if hybrid_handled_pages and modality.collection == COLLECTION_MAP[ChunkType.PAGE_IMAGE]:
                continue
            if doc_scoped and modality.collection == COLLECTION_MAP[ChunkType.FIGURE]:
                if not any(hint in q_lower for hint in FIGURE_HINTS):
                    continue
            if modality.collection == COLLECTION_MAP[ChunkType.TEXT]:
                hybrid_hits = self._hybrid_text_search(request, fetch_k)
                if hybrid_hits is not None:
                    if hybrid_hits:
                        result_lists.append(hybrid_hits)
                        list_weights.append(
                            col_weights.get(modality.collection, modality.base_weight)
                        )
                        hybrid_handled_pages = True
                    continue

            vector, actual_source = self._resolve_query_vector(
                modality,
                text_vector=text_vector,
                figure_vector=figure_vector,
                page_vector=page_vector,
            )
            hits = self.store.search(
                vector,
                collection_name=modality.collection,
                top_k=fetch_k,
                filters=request.filters or None,
            )
            if actual_source == "colpali":
                for hit in hits:
                    hit.strategy = RetrievalStrategy.COLPALI
            result_lists.append(hits)
            list_weights.append(col_weights.get(modality.collection, modality.base_weight))

        fused = reciprocal_rank_fusion(result_lists, k=self.rrf_k, weights=list_weights)
        candidates = _dedupe_by_content(fused, top_k=fetch_k)

        if self.reranker:
            results = self.reranker.rerank(
                request.query,
                candidates,
                top_n=request.top_k,
            )
        else:
            results = candidates[: request.top_k]

        results = prefer_substantive_contexts(results, request.top_k)
        return self._expand_parent_contexts(results)
