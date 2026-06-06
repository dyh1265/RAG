"""Tests for tenant_id scoping in QdrantStore."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("qdrant_client")

from backend.core.models import ChunkType, DocumentChunk, DocumentType, EmbeddedChunk
from backend.ingestion.stores.qdrant_store import QdrantStore, tenant_point_id


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


def _embedded_chunk(doc_id: str = "doc1", chunk_id: str | None = None) -> EmbeddedChunk:
    kwargs = {"id": chunk_id} if chunk_id else {}
    chunk = DocumentChunk(
        doc_id=doc_id,
        source_path="/data/raw/uploads/abc.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.TEXT,
        content="Sample text.",
        **kwargs,
    )
    return EmbeddedChunk(chunk=chunk, vector=[0.1, 0.2, 0.3, 0.4], model_name="test")


def test_upsert_stamps_tenant_id_in_payload():
    store = _make_store()
    store.upsert([_embedded_chunk()], tenant_id="tenant-42")

    call = store.client.upsert.call_args
    points = call.kwargs["points"]
    assert points[0].payload["tenant_id"] == "tenant-42"
    assert points[0].payload["doc_id"] == "doc1"


def test_upsert_namespaces_point_id_by_tenant():
    """Point id must be tenant-scoped, with the original chunk id kept in payload."""
    store = _make_store()
    store.upsert([_embedded_chunk(chunk_id="chunk-xyz")], tenant_id="tenant-42")

    points = store.client.upsert.call_args.kwargs["points"]
    assert points[0].id == tenant_point_id("tenant-42", "chunk-xyz")
    assert points[0].id != "chunk-xyz"
    assert points[0].payload["chunk_id"] == "chunk-xyz"


def test_upsert_same_chunk_id_differs_across_tenants():
    """Two tenants ingesting an identical deterministic chunk id must not collide."""
    store_a = _make_store()
    store_a.upsert([_embedded_chunk(chunk_id="shared")], tenant_id="tenant-A")
    id_a = store_a.client.upsert.call_args.kwargs["points"][0].id

    store_b = _make_store()
    store_b.upsert([_embedded_chunk(chunk_id="shared")], tenant_id="tenant-B")
    id_b = store_b.client.upsert.call_args.kwargs["points"][0].id

    assert id_a != id_b


def test_payload_to_chunk_restores_original_chunk_id():
    payload = {
        "doc_id": "doc-1",
        "chunk_id": "original-chunk-id",
        "source_path": "/data/report.pdf",
        "chunk_type": "text",
        "content": "Revenue grew.",
    }
    chunk = QdrantStore._payload_to_chunk(payload, "namespaced-point-id")
    assert chunk.id == "original-chunk-id"


def test_get_chunks_by_ids_resolves_tenant_point_ids():
    """parent-expand passes original ids; the store maps them to namespaced ids."""
    store = _make_store()
    store.client.retrieve.return_value = []

    store.get_chunks_by_ids("text_chunks", {"parent-1"}, tenant_id="tenant-42")

    requested = set(store.client.retrieve.call_args.kwargs["ids"])
    assert tenant_point_id("tenant-42", "parent-1") in requested
    # Raw id retained so legacy points written before namespacing still resolve.
    assert "parent-1" in requested


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
