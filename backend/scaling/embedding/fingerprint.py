"""Content hashing and document fingerprinting for skip-re-embed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.core.models import DocumentChunk


# Bytes sampled from the head of the file for fingerprinting.
# Big enough to detect content edits, small enough to keep ingest skip checks O(ms).
_DOC_FINGERPRINT_HEAD_BYTES = 64 * 1024


def doc_fingerprint(path: Path) -> str:
    """
    Stable fingerprint for fast change detection.

    Combines size + mtime + a hash of the first ~64 KB of content. The content
    sample makes the fingerprint robust to filesystems where size and mtime can
    collide for distinct writes (NTFS sub-tick mtime, etc.).
    """
    stat = path.stat()
    head_hash = hashlib.sha256()
    with path.open("rb") as fh:
        head_hash.update(fh.read(_DOC_FINGERPRINT_HEAD_BYTES))
    payload = f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}:{head_hash.hexdigest()}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def chunk_embed_key(chunk: DocumentChunk) -> str:
    """Hash of embed inputs — enriched text plus image path when present."""
    parts = [chunk.enriched_content]
    if chunk.image_path:
        parts.append(chunk.image_path)
        img = Path(chunk.image_path)
        if img.exists():
            stat = img.stat()
            parts.append(f"{stat.st_size}:{stat.st_mtime_ns}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def meta_key(doc_id: str) -> str:
    return f"ingest:meta:{doc_id}"


def serialize_meta(fingerprint: str, chunk_keys: dict[str, str]) -> str:
    return json.dumps({"fingerprint": fingerprint, "chunk_keys": chunk_keys})


def deserialize_meta(raw: str) -> dict:
    return json.loads(raw)
