"""Tests for QdrantStore helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.core.models import DocumentType
from backend.ingestion.stores.qdrant_store import (
    COLPALI_PAGE_DIM,
    TEXT_PAGE_DIM,
    QdrantStore,
    page_index_status,
)


def test_page_index_status_ok_for_colpali():
    store = MagicMock()
    store.collection_vector_size.return_value = COLPALI_PAGE_DIM
    assert page_index_status(store, use_colpali=True) is None


def test_page_index_status_warns_on_dim_mismatch():
    store = MagicMock()
    store.collection_vector_size.return_value = TEXT_PAGE_DIM
    msg = page_index_status(store, use_colpali=True)
    assert msg is not None
    assert str(COLPALI_PAGE_DIM) in msg
    assert "Re-run" in msg


def test_page_index_status_warns_when_collection_missing():
    store = MagicMock()
    store.collection_vector_size.return_value = None
    msg = page_index_status(store, use_colpali=True)
    assert msg is not None
    assert "page_chunks" in msg


def test_search_returns_empty_when_collection_missing():
    store = MagicMock()
    store.client.get_collections.return_value.collections = []

    qs = QdrantStore.__new__(QdrantStore)
    qs._client = store.client
    qs.upsert_batch_size = 64
    assert qs.search([0.1, 0.2], collection_name="text_chunks", top_k=5) == []
    store.client.query_points.assert_not_called()


def test_payload_to_chunk_restores_video_doc_type():
    payload = {
        "doc_id": "youtube_abc123",
        "source_path": "youtube:abc123",
        "doc_type": DocumentType.VIDEO.value,
        "chunk_type": "transcript",
        "content": "The speaker explains treatment heterogeneity.",
    }
    chunk = QdrantStore._payload_to_chunk(payload, "p1")
    assert chunk.doc_type == DocumentType.VIDEO


def test_payload_to_chunk_defaults_legacy_payload_to_pdf():
    # Older points were written before doc_type was stored.
    payload = {
        "doc_id": "doc-1",
        "source_path": "/data/report.pdf",
        "chunk_type": "text",
        "content": "Revenue grew.",
    }
    chunk = QdrantStore._payload_to_chunk(payload, "p2")
    assert chunk.doc_type == DocumentType.PDF


def test_payload_to_chunk_falls_back_on_unknown_doc_type():
    payload = {
        "doc_id": "doc-1",
        "source_path": "/data/report.pdf",
        "doc_type": "not-a-real-type",
        "chunk_type": "text",
        "content": "Revenue grew.",
    }
    chunk = QdrantStore._payload_to_chunk(payload, "p3")
    assert chunk.doc_type == DocumentType.PDF
