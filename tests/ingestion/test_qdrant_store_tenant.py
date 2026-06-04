"""Tests for tenant_id scoping in QdrantStore."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("qdrant_client")

from backend.core.models import ChunkType, DocumentChunk, DocumentType, EmbeddedChunk
from backend.ingestion.stores.qdrant_store import QdrantStore


def _make_store() -> QdrantStore:
    client = MagicMock()
    collection = MagicMock()
    collection.name = "text_chunks"
    client.get_collections.return_value.collections = [collection]
    vectors = MagicMock()
    vectors.size = 4
    info = MagicMock()
    info.config.params.vectors = vectors
    client.get_collection.return_value = info

    store = QdrantStore.__new__(QdrantStore)
    store.url = "http://localhost:6333"
    store.api_key = None
    store.upsert_batch_size = 64
    store._client = client
    return store


def _embedded_chunk(doc_id: str = "doc1") -> EmbeddedChunk:
    chunk = DocumentChunk(
        doc_id=doc_id,
        source_path="/data/raw/uploads/abc.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.TEXT,
        content="Sample text.",
    )
    return EmbeddedChunk(chunk=chunk, vector=[0.1, 0.2, 0.3, 0.4], model_name="test")


def test_upsert_stamps_tenant_id_in_payload():
    store = _make_store()
    store.upsert([_embedded_chunk()], tenant_id="tenant-42")

    call = store.client.upsert.call_args
    points = call.kwargs["points"]
    assert points[0].payload["tenant_id"] == "tenant-42"
    assert points[0].payload["doc_id"] == "doc1"


def test_delete_doc_includes_tenant_filter():
    store = _make_store()
    store.delete_doc("doc1", tenant_id="tenant-42")

    delete_call = store.client.delete.call_args
    selector = delete_call.kwargs["points_selector"]
    keys = [c.key for c in selector.filter.must]
    assert "doc_id" in keys
    assert "tenant_id" in keys


def test_list_documents_passes_tenant_scroll_filter():
    store = _make_store()
    record = MagicMock()
    record.payload = {"doc_id": "d1", "source_path": "/x.pdf"}
    store.client.scroll.return_value = ([record], None)

    docs = store.list_documents(limit=10, tenant_id="tenant-99")
    assert len(docs) == 1
    scroll_call = store.client.scroll.call_args
    scroll_filter = scroll_call.kwargs.get("scroll_filter")
    assert scroll_filter is not None
    keys = [c.key for c in scroll_filter.must]
    assert keys == ["tenant_id"]


def test_get_document_source_path_scopes_by_tenant():
    store = _make_store()
    record = MagicMock()
    record.payload = {"source_path": "/data/raw/x.pdf"}
    store.client.scroll.return_value = ([record], None)

    path = store.get_document_source_path("doc1", tenant_id="tenant-77")
    assert path == "/data/raw/x.pdf"
    scroll_filter = store.client.scroll.call_args.kwargs["scroll_filter"]
    keys = [c.key for c in scroll_filter.must]
    assert "doc_id" in keys
    assert "tenant_id" in keys
