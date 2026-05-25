"""Redis-backed embedding cache — hash(content) → vector."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.core.config import get_settings

if TYPE_CHECKING:
    import redis


class EmbeddingCache:
    """Cache embedding vectors keyed by content hash + model name."""

    PREFIX = "embed:v1:"

    def __init__(self, redis_url: str | None = None, ttl_seconds: int | None = None) -> None:
        settings = get_settings()
        self.redis_url = redis_url or settings.redis_url
        self.ttl = ttl_seconds if ttl_seconds is not None else settings.embedding_cache_ttl_seconds
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            try:
                import redis
            except ImportError as exc:
                raise ImportError("Install redis: pip install redis") from exc
            self._client = redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    def available(self) -> bool:
        try:
            self.client.ping()
            return True
        except Exception:
            return False

    def _key(self, content_hash: str, model_name: str) -> str:
        safe_model = model_name.replace("/", "_")
        return f"{self.PREFIX}{safe_model}:{content_hash}"

    def get_vector(self, content_hash: str, model_name: str) -> list[float] | None:
        raw = self.client.get(self._key(content_hash, model_name))
        if raw is None:
            return None
        return json.loads(raw)

    def set_vector(self, content_hash: str, model_name: str, vector: list[float]) -> None:
        key = self._key(content_hash, model_name)
        self.client.setex(key, self.ttl, json.dumps(vector))

    def get_doc_meta(self, doc_id: str) -> dict | None:
        from backend.scaling.embedding.fingerprint import deserialize_meta, meta_key

        raw = self.client.get(meta_key(doc_id))
        if raw is None:
            return None
        return deserialize_meta(raw)

    def set_doc_meta(self, doc_id: str, fingerprint: str, chunk_keys: dict[str, str]) -> None:
        from backend.scaling.embedding.fingerprint import meta_key, serialize_meta

        self.client.set(meta_key(doc_id), serialize_meta(fingerprint, chunk_keys))

    def mark_ingest_done(self, path: str) -> None:
        self.client.sadd("ingest:done", path)

    def is_ingest_done(self, path: str) -> bool:
        return bool(self.client.sismember("ingest:done", path))

    def clear_ingest_done(self) -> None:
        self.client.delete("ingest:done")
