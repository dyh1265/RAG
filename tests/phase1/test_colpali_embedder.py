"""Tests for ColPali mean-pooling and embed routing."""

from __future__ import annotations

from unittest.mock import MagicMock

import torch

from phases.phase_01_multimodal_ingestion.embeddings.colpali_embedder import _pool_multi_vector
from phases.phase_01_multimodal_ingestion.embeddings.multimodal_embed import embed_chunks
from shared.models import ChunkType, EmbeddedChunk
from tests.phase1.conftest import make_chunk


def test_pool_multi_vector_mean_pools_and_normalises():
    embeddings = torch.tensor([[1.0, 0.0], [1.0, 0.0]])
    pooled = _pool_multi_vector(embeddings)
    assert len(pooled) == 2
    assert abs(pooled[0] - 1.0) < 1e-5
    assert abs(pooled[1]) < 1e-5


def test_embed_chunks_routes_pages_to_colpali_when_enabled():
    text_chunk = make_chunk(chunk_id="t1", chunk_type=ChunkType.TEXT)
    page_chunk = make_chunk(chunk_id="p1", chunk_type=ChunkType.PAGE_IMAGE)
    page_chunk = page_chunk.model_copy(update={"image_path": "/tmp/page1.png"})

    text_embedder = MagicMock()
    text_embedder.embed_chunks.return_value = [
        EmbeddedChunk(chunk=text_chunk, vector=[1.0], model_name="bge-m3")
    ]
    image_embedder = MagicMock()
    image_embedder.embed_figure_chunks.return_value = []
    colpali = MagicMock()
    colpali.embed_page_chunks.return_value = [
        EmbeddedChunk(chunk=page_chunk, vector=[0.5], model_name="colqwen2")
    ]

    result = embed_chunks(
        [text_chunk, page_chunk],
        text_embedder,
        image_embedder,
        colpali,
        use_colpali=True,
    )

    text_args = text_embedder.embed_chunks.call_args[0][0]
    assert all(c.chunk_type != ChunkType.PAGE_IMAGE for c in text_args)
    colpali.embed_page_chunks.assert_called_once()
    assert len(result) == 2
