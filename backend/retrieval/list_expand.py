"""Expand retrieval hits with sibling bullet-list items split across pages."""

from __future__ import annotations

import re

from backend.core.models import ChunkType, RetrievalStrategy, RetrievedContext
from backend.ingestion.stores.qdrant_store import COLLECTION_MAP, QdrantStore

# e.g. "- Logical view: Shows key system ideas and components."
_LIST_VIEW_ITEM = re.compile(
    r"^-\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+view:\s*.+",
    re.IGNORECASE | re.MULTILINE,
)

_LIST_INTRO_MARKERS = ("such as:", "viewpoints", "viewpoints,")


def _chunk_has_list_view_item(chunk) -> bool:
    return bool(_LIST_VIEW_ITEM.search(chunk.content.strip()))


def _chunk_has_list_intro(chunk) -> bool:
    lowered = chunk.content.lower()
    return any(marker in lowered for marker in _LIST_INTRO_MARKERS)


def _page_window(pages: set[int]) -> set[int]:
    if not pages:
        return set()
    lo, hi = min(pages), max(pages)
    return set(range(max(1, lo), hi + 2))


def expand_split_list_items(
    store: QdrantStore,
    doc_id: str,
    contexts: list[RetrievedContext],
    top_k: int,
) -> list[RetrievedContext]:
    """
    When list items were chunked per line across pages, ensure all siblings
    from the same doc/page window are included (e.g. four architectural views).
    """
    if not contexts or not doc_id:
        return contexts

    seed_pages: set[int] = set()
    for ctx in contexts:
        page = ctx.chunk.page_number
        if page is None:
            continue
        if _chunk_has_list_view_item(ctx.chunk) or _chunk_has_list_intro(ctx.chunk):
            seed_pages.add(page)

    if not seed_pages:
        return contexts

    pages = _page_window(seed_pages)
    corpus = store.scroll_collection(
        COLLECTION_MAP[ChunkType.TEXT],
        filters={"doc_id": doc_id},
    )

    sibling_map: dict[str, RetrievedContext] = {}
    for chunk in corpus:
        if chunk.page_number not in pages:
            continue
        if not _chunk_has_list_view_item(chunk):
            continue
        sibling_map[chunk.id] = RetrievedContext(
            chunk=chunk,
            score=99.0,
            strategy=RetrievalStrategy.DENSE,
            rank=0,
        )

    if not sibling_map:
        return contexts

    merged: list[RetrievedContext] = []
    seen: set[str] = set()

    # Keep original ranking for hits already retrieved.
    for ctx in contexts:
        if ctx.chunk.id in seen:
            continue
        seen.add(ctx.chunk.id)
        merged.append(ctx)

    # Inject any list siblings that dense search missed (often the next page).
    for ctx in sorted(sibling_map.values(), key=lambda c: (c.chunk.page_number or 0, c.chunk.content)):
        if ctx.chunk.id in seen:
            continue
        seen.add(ctx.chunk.id)
        merged.append(ctx)

    # Drop lowest-scoring filler only if we exceed top_k; never drop injected siblings.
    sibling_ids = set(sibling_map)
    if len(merged) > top_k:
        protected = [ctx for ctx in merged if ctx.chunk.id in sibling_ids]
        optional = [ctx for ctx in merged if ctx.chunk.id not in sibling_ids]
        optional.sort(key=lambda c: c.score, reverse=True)
        keep_optional = max(0, top_k - len(protected))
        merged = protected + optional[:keep_optional]
        merged.sort(
            key=lambda c: (
                0 if c.chunk.id in sibling_ids else 1,
                -(c.score or 0),
            ),
        )

    reranked: list[RetrievedContext] = []
    for rank, ctx in enumerate(merged, start=1):
        reranked.append(
            RetrievedContext(
                chunk=ctx.chunk,
                score=ctx.score,
                strategy=ctx.strategy,
                rank=rank,
            )
        )
    return reranked
