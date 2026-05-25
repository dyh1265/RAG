"""Tests for multimodal embed chunk routing."""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.ingestion.embeddings.multimodal_embed import embed_chunks
from backend.core.models import ChunkType, EmbeddedChunk
from tests._factories import make_chunk


def test_embed_chunks_routes_by_type():
    text_chunk = make_chunk(chunk_id="t1", chunk_type=ChunkType.TEXT, content="text")
    table_chunk = make_chunk(chunk_id="t2", chunk_type=ChunkType.TABLE, content="table")
    figure_chunk = make_chunk(
        chunk_id="f1",
        chunk_type=ChunkType.FIGURE,
        content="figure caption",
        page_number=2,
    )
    figure_chunk = figure_chunk.model_copy(update={"image_path": "/tmp/fig.png"})

    text_embedder = MagicMock()
    text_embedder.embed_chunks.return_value = [
        EmbeddedChunk(chunk=text_chunk, vector=[1.0], model_name="bge-m3"),
        EmbeddedChunk(chunk=table_chunk, vector=[2.0], model_name="bge-m3"),
    ]
    image_embedder = MagicMock()
    image_embedder.embed_figure_chunks.return_value = [
        EmbeddedChunk(chunk=figure_chunk, vector=[3.0], model_name="clip"),
    ]

    result = embed_chunks([text_chunk, table_chunk, figure_chunk], text_embedder, image_embedder)

    text_embedder.embed_chunks.assert_called_once()
    text_args = text_embedder.embed_chunks.call_args[0][0]
    assert {c.chunk_type for c in text_args} == {ChunkType.TEXT, ChunkType.TABLE}

    image_embedder.embed_figure_chunks.assert_called_once()
    figure_args = image_embedder.embed_figure_chunks.call_args[0][0]
    assert len(figure_args) == 1
    assert figure_args[0].chunk_type == ChunkType.FIGURE

    assert len(result) == 3
