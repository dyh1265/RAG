"""Smoke tests for the unified documind package facade."""

from __future__ import annotations


def test_documind_top_level_exports():
    import documind

    assert documind.RAGPipeline is not None
    assert documind.DocuMind is not None
    assert documind.get_settings is not None
    assert documind.__version__ == "0.1.0"


def test_documind_core_reexports():
    from documind.core import RAGPipeline, QueryRequest

    assert RAGPipeline.__name__ == "RAGPipeline"
    assert QueryRequest.__name__ == "QueryRequest"


def test_documind_ingestion_reexports():
    from documind.ingestion import QdrantStore, COLLECTION_MAP

    assert "text_chunks" in COLLECTION_MAP.values()
    assert QdrantStore.__name__ == "QdrantStore"


def test_documind_production_app():
    from documind.production import app

    assert app.title == "Advanced RAG API"


def test_legacy_phase_import_shim():
    from phases._legacy import install_legacy_imports

    install_legacy_imports()
    from phase_01_multimodal_ingestion.stores.qdrant_store import QdrantStore

    assert QdrantStore.__name__ == "QdrantStore"
