"""Cross-encoder reranker for fused retrieval candidates."""

from __future__ import annotations

from shared.config import get_settings
from shared.models import RetrievedContext, RetrievalStrategy


class CrossEncoderReranker:
    """
    Re-score (query, passage) pairs with a cross-encoder.

    Install: pip install sentence-transformers
    Default model: BAAI/bge-reranker-v2-m3 (from shared/config.py)
    """

    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.reranker_model
        self.device = device or settings.embedding_device
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            raise ImportError("Install sentence-transformers: pip install sentence-transformers")
        self._model = CrossEncoder(self.model_name, device=self.device)

    def rerank(
        self,
        query: str,
        contexts: list[RetrievedContext],
        top_n: int | None = None,
    ) -> list[RetrievedContext]:
        """Return contexts re-ordered by cross-encoder relevance scores."""
        if not contexts:
            return []

        settings = get_settings()
        limit = top_n or settings.reranker_top_n
        limit = min(limit, len(contexts))

        self._ensure_loaded()
        pairs = [(query, ctx.chunk.content) for ctx in contexts]
        scores = self._model.predict(pairs)

        ranked = sorted(
            zip(contexts, scores),
            key=lambda item: float(item[1]),
            reverse=True,
        )

        results: list[RetrievedContext] = []
        for rank, (ctx, score) in enumerate(ranked[:limit], start=1):
            results.append(
                RetrievedContext(
                    chunk=ctx.chunk,
                    score=float(score),
                    strategy=RetrievalStrategy.HYBRID,
                    rank=rank,
                )
            )
        return results
