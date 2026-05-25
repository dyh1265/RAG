"""
Text embedder using sentence-transformers (bge-m3 by default).
Supports batched encoding and returns normalised vectors.
"""

from __future__ import annotations


from shared.config import get_settings
from shared.models import DocumentChunk, EmbeddedChunk


class TextEmbedder:
    """
    Wraps sentence-transformers for text embedding.

    Install: pip install sentence-transformers

    Usage
    -----
    embedder = TextEmbedder()
    embedded = embedder.embed_chunks(chunks)
    """

    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.text_embedding_model
        self.device = device or settings.embedding_device
        self.batch_size = settings.embedding_batch_size
        self._model = None  # lazy load

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "Install sentence-transformers: pip install sentence-transformers"
                ) from exc
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of strings, returns list of float vectors."""
        vectors = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 50,
        )
        return vectors.tolist()

    def embed_chunks(self, chunks: list[DocumentChunk]) -> list[EmbeddedChunk]:
        """Embed DocumentChunks using their enriched_content."""
        texts = [c.enriched_content for c in chunks]
        vectors = self.embed_texts(texts)
        return [
            EmbeddedChunk(chunk=chunk, vector=vec, model_name=self.model_name)
            for chunk, vec in zip(chunks, vectors)
        ]

    @property
    def vector_size(self) -> int:
        return self.model.get_sentence_embedding_dimension()
