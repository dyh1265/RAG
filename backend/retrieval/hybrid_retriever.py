"""
Hybrid retriever: BM25 (sparse) + dense vector search, fused with Reciprocal Rank Fusion.

This is the recommended baseline retriever. RRF is parameter-free and
consistently outperforms naive score averaging.
"""

from __future__ import annotations

from backend.retrieval.chunk_filters import is_substantive_content
from backend.core.models import ChunkType, DocumentChunk, QueryRequest, RetrievalStrategy, RetrievedContext

# doc_id -> (corpus_size, BM25Okapi index)
_BM25_CACHE: dict[str, tuple[int, object]] = {}


def invalidate_bm25_cache(doc_id: str | None = None) -> None:
    """Drop cached BM25 indexes (call after re-ingest)."""
    if doc_id is None:
        _BM25_CACHE.clear()
        return
    _BM25_CACHE.pop(doc_id, None)


def reciprocal_rank_fusion(
    result_lists: list[list[RetrievedContext]],
    k: int = 60,
    weights: list[float] | None = None,
) -> list[RetrievedContext]:
    """
    Fuse multiple ranked lists using Reciprocal Rank Fusion.

    RRF score for document d = sum over all lists L of weight_L / (k + rank_of_d_in_L)
    Higher score = more relevant.

    k=60 is the standard default from the original RRF paper (Cormack et al., 2009).
    """
    list_weights = weights or [1.0] * len(result_lists)
    scores: dict[str, float] = {}
    chunk_map: dict[str, RetrievedContext] = {}

    for list_weight, result_list in zip(list_weights, result_lists):
        for rank, ctx in enumerate(result_list, start=1):
            chunk_id = ctx.chunk.id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + list_weight / (k + rank)
            chunk_map[chunk_id] = ctx

    sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    fused = []
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


def _index_text(chunk: DocumentChunk) -> str:
    """Text used for BM25 — matches dense embedding input."""
    return chunk.enriched_content


def _boost_section_chunks(
    query: str,
    results: list[RetrievedContext],
) -> list[RetrievedContext]:
    """Prefer page/text chunks that match section-style questions (lists, objectives, etc.)."""
    q = query.lower()
    triggers = (
        "objective",
        "contents",
        "summary",
        "what are",
        "what is",
        "list",
        "practices",
        "principles",
        "steps",
    )
    if not any(token in q for token in triggers):
        return results

    def rank_score(result: RetrievedContext) -> float:
        content = result.chunk.content
        lowered = content.lower()
        score = result.score
        if not is_substantive_content(content):
            return score - 100.0
        if "objective of this chapter" in lowered or "objectives" in lowered:
            score += 10.0
        if "- " in content or "■" in content or "•" in content:
            score += 5.0
        if result.chunk.chunk_type == ChunkType.PAGE_IMAGE:
            score += 2.0
        return score

    reranked = sorted(results, key=rank_score, reverse=True)
    for rank, ctx in enumerate(reranked, start=1):
        ctx.rank = rank
    return reranked


class HybridRetriever:
    """
    Combines BM25 sparse retrieval with dense vector search via RRF.

    Usage
    -----
    retriever = HybridRetriever(corpus_chunks, embedder, vector_store, doc_id="abc")
    results = retriever.retrieve(QueryRequest(query="...", top_k=5))

    Install: pip install rank-bm25
    """

    def __init__(
        self,
        corpus_chunks: list[DocumentChunk],
        embedder,
        vector_store,
        *,
        doc_id: str | None = None,
    ) -> None:
        self.corpus_chunks = corpus_chunks
        self.embedder = embedder
        self.vector_store = vector_store
        self.doc_id = doc_id or (corpus_chunks[0].doc_id if corpus_chunks else "")
        self._bm25 = None

    @property
    def bm25(self):
        if self._bm25 is None:
            cache_key = self.doc_id
            cached = _BM25_CACHE.get(cache_key)
            if cached and cached[0] == len(self.corpus_chunks):
                self._bm25 = cached[1]
                return self._bm25

            try:
                from rank_bm25 import BM25Okapi
            except ImportError:
                raise ImportError("Install rank-bm25: pip install rank-bm25")
            tokenised = [_index_text(c).lower().split() for c in self.corpus_chunks]
            self._bm25 = BM25Okapi(tokenised)
            if cache_key:
                _BM25_CACHE[cache_key] = (len(self.corpus_chunks), self._bm25)
        return self._bm25

    def _sparse_search(self, query: str, top_k: int) -> list[RetrievedContext]:
        tokenised_query = query.lower().split()
        scores = self.bm25.get_scores(tokenised_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [
            RetrievedContext(
                chunk=self.corpus_chunks[i],
                score=float(scores[i]),
                strategy=RetrievalStrategy.SPARSE,
                rank=rank + 1,
            )
            for rank, i in enumerate(top_indices)
        ]

    def _dense_search(
        self,
        query: str,
        top_k: int,
        filters: dict | None = None,
    ) -> list[RetrievedContext]:
        query_vector = self.embedder.embed_texts([query])[0]
        return self.vector_store.search(
            query_vector,
            collection_name="text_chunks",
            top_k=top_k,
            filters=filters,
        )

    def retrieve(self, request: QueryRequest) -> list[RetrievedContext]:
        fetch_k = request.top_k * 3
        sparse = self._sparse_search(request.query, top_k=fetch_k)
        dense = self._dense_search(
            request.query,
            top_k=fetch_k,
            filters=request.filters or None,
        )
        has_page_corpus = any(
            chunk.chunk_type == ChunkType.PAGE_IMAGE for chunk in self.corpus_chunks
        )
        sparse_weight = 2.5 if has_page_corpus else 1.0
        fused = reciprocal_rank_fusion(
            [sparse, dense],
            k=60,
            weights=[sparse_weight, 1.0],
        )
        if has_page_corpus:
            fused = _boost_section_chunks(request.query, fused)
        return fused[: request.top_k]
