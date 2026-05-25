"""Tests for Redis embedding cache (mocked client)."""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.scaling.embedding.redis_cache import EmbeddingCache


def test_cache_get_set_vector(monkeypatch):
    store: dict[str, str] = {}
    client = MagicMock()
    client.ping.return_value = True
    client.get.side_effect = lambda k: store.get(k)
    client.setex.side_effect = lambda k, _ttl, v: store.__setitem__(k, v) or True

    cache = EmbeddingCache(redis_url="redis://fake/0")
    monkeypatch.setattr(cache, "_client", client)
    monkeypatch.setattr(cache, "available", lambda: True)

    assert cache.get_vector("abc", "model/x") is None
    cache.set_vector("abc", "model/x", [0.1, 0.2])
    assert cache.get_vector("abc", "model/x") == [0.1, 0.2]


def test_doc_meta_roundtrip(monkeypatch):
    store: dict[str, str] = {}
    client = MagicMock()
    client.ping.return_value = True
    client.get.side_effect = lambda k: store.get(k)
    client.set.side_effect = lambda k, v: store.__setitem__(k, v) or True

    cache = EmbeddingCache(redis_url="redis://fake/0")
    monkeypatch.setattr(cache, "_client", client)
    monkeypatch.setattr(cache, "available", lambda: True)

    cache.set_doc_meta("doc1", "fp123", {"c1": "h1"})
    meta = cache.get_doc_meta("doc1")
    assert meta["fingerprint"] == "fp123"
    assert meta["chunk_keys"]["c1"] == "h1"
