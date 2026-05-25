"""Tests for QdrantStore helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from phases.phase_01_multimodal_ingestion.stores.qdrant_store import (
    COLPALI_PAGE_DIM,
    TEXT_PAGE_DIM,
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
    from phases.phase_01_multimodal_ingestion.stores.qdrant_store import QdrantStore

    qs = QdrantStore.__new__(QdrantStore)
    qs._client = store.client
    qs.upsert_batch_size = 64
    assert qs.search([0.1, 0.2], collection_name="text_chunks", top_k=5) == []
    store.client.query_points.assert_not_called()
