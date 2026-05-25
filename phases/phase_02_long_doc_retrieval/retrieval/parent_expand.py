"""Expand child chunk hits to their parent chunks for richer context."""

from __future__ import annotations

from shared.models import RetrievedContext


def collect_parent_ids(contexts: list[RetrievedContext]) -> set[str]:
    """Return parent_chunk_id values referenced by retrieved child chunks."""
    parent_ids: set[str] = set()
    for ctx in contexts:
        parent_id = ctx.chunk.metadata.get("parent_chunk_id")
        if parent_id:
            parent_ids.add(str(parent_id))
    return parent_ids


def expand_to_parents(
    contexts: list[RetrievedContext],
    parent_map: dict[str, RetrievedContext],
) -> list[RetrievedContext]:
    """
    Replace child hits with parent chunks when a parent is available.

    Keeps the child's relevance score on the expanded parent context.
    """
    if not parent_map:
        return contexts

    expanded: list[RetrievedContext] = []
    seen: set[str] = set()

    for ctx in contexts:
        parent_id = ctx.chunk.metadata.get("parent_chunk_id")
        if parent_id and str(parent_id) in parent_map:
            parent_ctx = parent_map[str(parent_id)]
            if parent_ctx.chunk.id in seen:
                continue
            seen.add(parent_ctx.chunk.id)
            expanded.append(
                RetrievedContext(
                    chunk=parent_ctx.chunk,
                    score=ctx.score,
                    strategy=ctx.strategy,
                    rank=len(expanded) + 1,
                )
            )
            continue

        if ctx.chunk.id in seen:
            continue
        seen.add(ctx.chunk.id)
        expanded.append(
            RetrievedContext(
                chunk=ctx.chunk,
                score=ctx.score,
                strategy=ctx.strategy,
                rank=len(expanded) + 1,
            )
        )

    return expanded
