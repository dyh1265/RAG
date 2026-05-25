"""Tests for SemanticChunker grouping logic."""

from __future__ import annotations

from unittest.mock import MagicMock

from phases.phase_02_long_doc_retrieval.chunking.semantic_chunker import SemanticChunker, _split_sentences
from shared.models import ChunkType, DocumentChunk, DocumentType


def test_split_sentences():
    text = "First sentence. Second sentence! Third?"
    parts = _split_sentences(text)
    assert len(parts) == 3


def test_semantic_chunker_splits_on_low_similarity():
    doc = DocumentChunk(
        id="parent",
        doc_id="d1",
        source_path="x.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.TEXT,
        content=(
            "Agile software development uses incremental releases. "
            "Teams deliver working software every two weeks. "
            "Configuration management tracks component versions. "
            "Baselines are controlled collections of component versions."
        ),
        page_number=75,
    )

    embedder = MagicMock()
    # high sim within topic pairs, low sim at topic boundary (sentence 2 vs 3)
    embedder.embed_texts.return_value = [
        [1.0, 0.0],
        [0.95, 0.05],
        [0.2, 0.9],
        [0.15, 0.95],
    ]

    chunker = SemanticChunker(embedder=embedder, max_chunk_size=500, similarity_threshold=0.75)
    children = chunker.chunk([doc])

    assert len(children) >= 2
    assert all(child.metadata.get("parent_chunk_id") == "parent" for child in children)
    assert all(child.metadata.get("chunker") == "semantic" for child in children)
