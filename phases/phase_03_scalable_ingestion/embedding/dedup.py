"""MinHash / LSH near-duplicate detection before embedding."""

from __future__ import annotations

from datasketch import MinHash, MinHashLSH

from shared.config import get_settings
from shared.models import DocumentChunk


def _minhash(text: str, num_perm: int = 128) -> MinHash:
    mh = MinHash(num_perm=num_perm)
    for token in text.lower().split():
        if len(token) > 2:
            mh.update(token.encode())
    return mh


def deduplicate_chunks(
    chunks: list[DocumentChunk],
    *,
    threshold: float | None = None,
) -> tuple[list[DocumentChunk], int]:
    """
    Drop near-duplicate chunks within a single document ingest batch.

    Returns (kept_chunks, num_removed).
    """
    if len(chunks) < 2:
        return chunks, 0

    settings = get_settings()
    threshold = threshold if threshold is not None else settings.dedup_similarity_threshold
    lsh = MinHashLSH(threshold=threshold, num_perm=128)
    kept: list[DocumentChunk] = []
    removed = 0

    for chunk in chunks:
        text = chunk.enriched_content.strip()
        if len(text) < 40:
            kept.append(chunk)
            continue
        mh = _minhash(text)
        if lsh.query(mh):
            removed += 1
            continue
        lsh.insert(chunk.id, mh)
        kept.append(chunk)

    return kept, removed
