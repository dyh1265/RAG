"""Tests for retrieval chunk filtering."""

from __future__ import annotations

from backend.retrieval.chunk_filters import (
    is_substantive_content,
    prefer_substantive_contexts,
)
from backend.core.models import ChunkType
from tests._factories import make_context


def test_is_substantive_content_rejects_image_stub():
    assert not is_substantive_content("Page 17 image (no extractable text)")
    assert not is_substantive_content("Figure on page 1")


def test_prefer_substantive_contexts_orders_text_first():
    stub = make_context(
        chunk_id="stub",
        chunk_type=ChunkType.PAGE_IMAGE,
        content="Page 1 image (no extractable text)",
        score=0.9,
    )
    text = make_context(
        chunk_id="text",
        content="The objective of this chapter is to introduce software testing and processes.",
        score=0.1,
    )
    ordered = prefer_substantive_contexts([stub, text], top_k=2)
    assert ordered[0].chunk.id == "text"
