"""
ColPali / ColQwen2 embedder for full-page document images.

Uses colpali-engine multi-vector outputs, mean-pooled to a single dense vector
for Qdrant cosine search. Native MaxSim multi-vector search can be added later.
"""

from __future__ import annotations

from pathlib import Path

import torch

from backend.core.config import get_settings
from backend.core.models import DocumentChunk, EmbeddedChunk


def _pool_multi_vector(
    embeddings: torch.Tensor,
    attention_mask: torch.Tensor | None = None,
) -> list[float]:
    """Mean-pool token/patch embeddings into one L2-normalised vector."""
    if embeddings.dim() == 3:
        embeddings = embeddings[0]
    if attention_mask is not None:
        mask = attention_mask[0].bool() if attention_mask.dim() == 2 else attention_mask.bool()
        if mask.any():
            embeddings = embeddings[mask]
    if embeddings.numel() == 0:
        raise ValueError("ColPali produced empty embeddings after masking")
    pooled = embeddings.mean(dim=0)
    pooled = pooled / pooled.norm().clamp(min=1e-12)
    return pooled.float().cpu().tolist()


class ColPaliEmbedder:
    """
    Wraps ColQwen2 (or compatible ColVision model) for page image embedding.

    Install: pip install colpali-engine
    Default model: vidore/colqwen2-v1.0 (override with COLPALI_MODEL; try
    vidore/colSmol-500M on CPU for faster/smaller runs).

    Usage
    -----
    embedder = ColPaliEmbedder()
    vectors = embedder.embed_images(["path/to/page.png"])
    query_vec = embedder.embed_query("revenue chart on page 2")
    """

    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.colpali_model
        self.device = device or settings.embedding_device
        self._model = None
        self._processor = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from colpali_engine.models import ColQwen2, ColQwen2Processor
        except ImportError as exc:
            raise ImportError("Install colpali-engine: pip install colpali-engine") from exc

        dtype = torch.float32 if self.device == "cpu" else torch.bfloat16
        self._model = ColQwen2.from_pretrained(
            self.model_name,
            torch_dtype=dtype,
        ).eval()
        self._model.to(self.device)
        self._processor = ColQwen2Processor.from_pretrained(self.model_name)

    def embed_images(self, image_paths: list[str | Path]) -> list[list[float]]:
        """Embed page PNGs; returns mean-pooled 128-dim vectors (ColQwen2)."""
        from PIL import Image

        self._ensure_loaded()
        vectors: list[list[float]] = []

        for path in image_paths:
            with Image.open(path).convert("RGB") as img:
                batch = self._processor.process_images([img]).to(self._model.device)
            with torch.no_grad():
                embeddings = self._model(**batch)
            vectors.append(_pool_multi_vector(embeddings, batch.get("attention_mask")))

        return vectors

    def embed_query(self, text: str) -> list[float]:
        """Encode a text query in ColPali space for searching page_chunks."""
        self._ensure_loaded()
        batch = self._processor.process_queries([text]).to(self._model.device)
        with torch.no_grad():
            embeddings = self._model(**batch)
        return _pool_multi_vector(embeddings, batch.get("attention_mask"))

    def embed_page_chunks(self, chunks: list[DocumentChunk]) -> list[EmbeddedChunk]:
        """Embed page image chunks from their full-page PNG paths."""
        if not chunks:
            return []
        paths = []
        for chunk in chunks:
            if not chunk.image_path:
                raise ValueError(f"Page chunk {chunk.id} has no image_path")
            paths.append(chunk.image_path)
        vectors = self.embed_images(paths)
        return [
            EmbeddedChunk(chunk=chunk, vector=vec, model_name=self.model_name)
            for chunk, vec in zip(chunks, vectors)
        ]

    @property
    def vector_size(self) -> int:
        self._ensure_loaded()
        return int(getattr(self._model, "dim", 128))
