"""Helpers to drop placeholder image chunks from retrieval results."""

from __future__ import annotations

from backend.core.models import RetrievedContext


def is_substantive_content(content: str, *, min_len: int = 40) -> bool:
    """True when chunk text is useful for LLM grounding (not a page/figure stub)."""
    text = content.strip()
    if len(text) < min_len:
        return False
    lowered = text.lower()
    if "no extractable text" in lowered:
        return False
    if text.startswith("Figure on page") and len(text) < 100:
        return False
    return True


def prefer_substantive_contexts(
    contexts: list[RetrievedContext],
    top_k: int,
) -> list[RetrievedContext]:
    """Put text-bearing chunks first; keep placeholders only as fallback."""
    substantive = [ctx for ctx in contexts if is_substantive_content(ctx.chunk.content)]
    if not substantive:
        return contexts[:top_k]
    filler = [ctx for ctx in contexts if ctx not in substantive]
    merged = substantive + filler
    reranked: list[RetrievedContext] = []
    for rank, ctx in enumerate(merged[:top_k], start=1):
        reranked.append(
            RetrievedContext(
                chunk=ctx.chunk,
                score=ctx.score,
                strategy=ctx.strategy,
                rank=rank,
            )
        )
    return reranked
