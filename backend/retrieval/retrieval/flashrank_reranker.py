"""FlashRank reranker — lightweight cross-encoder alternative for Phase 2."""

from __future__ import annotations

from backend.core.models import RetrievedContext, RetrievalStrategy


class FlashRankReranker:
    """
    Re-score candidates with FlashRank (ONNX, no torch dependency).

    Install: pip install flashrank
    Default model: ms-marco-MiniLM-L-12-v2 (~40MB)
    """

    def __init__(self, model_name: str = "ms-marco-MiniLM-L-12-v2") -> None:
        self.model_name = model_name
        self._ranker = None

    def _ensure_loaded(self) -> None:
        if self._ranker is not None:
            return
        try:
            from flashrank import Ranker
        except ImportError:
            raise ImportError("Install flashrank: pip install flashrank") from None
        self._ranker = Ranker(model_name=self.model_name)

    def rerank(
        self,
        query: str,
        contexts: list[RetrievedContext],
        top_n: int | None = None,
    ) -> list[RetrievedContext]:
        if not contexts:
            return []

        limit = top_n if top_n is not None else len(contexts)
        limit = min(limit, len(contexts))

        self._ensure_loaded()
        from flashrank import RerankRequest

        passages = [
            {
                "id": str(idx),
                "text": ctx.chunk.enriched_content,
                "meta": {"chunk_id": ctx.chunk.id},
            }
            for idx, ctx in enumerate(contexts)
        ]
        ranked = self._ranker.rerank(RerankRequest(query=query, passages=passages))

        id_to_ctx = {str(idx): ctx for idx, ctx in enumerate(contexts)}
        results: list[RetrievedContext] = []
        for rank, hit in enumerate(ranked[:limit], start=1):
            ctx = id_to_ctx[str(hit["id"])]
            score = float(hit.get("score", ctx.score))
            results.append(
                RetrievedContext(
                    chunk=ctx.chunk,
                    score=score,
                    strategy=RetrievalStrategy.HYBRID,
                    rank=rank,
                )
            )
        return results
