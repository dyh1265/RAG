"""Content hashing and document fingerprinting for skip-re-embed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from shared.models import DocumentChunk


def doc_fingerprint(path: Path) -> str:
    """Stable fingerprint from file size + mtime (fast change detection)."""
    stat = path.stat()
    payload = f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}"
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
