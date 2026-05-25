"""
Semantic chunker — split text at embedding-similarity breakpoints.

Groups consecutive sentences while adjacent cosine similarity stays above
``similarity_threshold``, then starts a new chunk when the topic shifts.
"""

from __future__ import annotations

import math
import re

from shared.config import get_settings
from shared.models import DocumentChunk
from phases.phase_01_multimodal_ingestion.parsers.base_parser import stable_chunk_id, stable_split_chunk_id
from phases.phase_01_multimodal_ingestion.embeddings.text_embedder import TextEmbedder
from .base_chunker import BaseChunker

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text.strip())
    return [part.strip() for part in parts if part.strip()]


class SemanticChunker(BaseChunker):
    """
    Split documents at semantic boundaries using sentence embeddings.

    Install: sentence-transformers (already required for Phase 1)
    """

    def __init__(
        self,
        embedder: TextEmbedder | None = None,
        *,
        max_chunk_size: int | None = None,
        similarity_threshold: float | None = None,
    ) -> None:
        settings = get_settings()
        self.embedder = embedder
        self.max_chunk_size = max_chunk_size or settings.max_chunk_size
        self.similarity_threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else settings.semantic_chunk_threshold
        )

    def _get_embedder(self) -> TextEmbedder:
        if self.embedder is None:
            self.embedder = TextEmbedder()
        return self.embedder

    def _group_sentences(self, sentences: list[str]) -> list[str]:
        if len(sentences) <= 1:
            return [" ".join(sentences)] if sentences else []

        embeddings = self._get_embedder().embed_texts(sentences)
        groups: list[list[str]] = [[sentences[0]]]
        current_len = len(sentences[0])

        for idx in range(1, len(sentences)):
            sim = _cosine(embeddings[idx - 1], embeddings[idx])
            sentence = sentences[idx]
            next_len = current_len + len(sentence) + 1
            topic_shift = sim < self.similarity_threshold
            size_exceeded = next_len > self.max_chunk_size and len(groups[-1]) >= 1

            if topic_shift or size_exceeded:
                groups.append([sentence])
                current_len = len(sentence)
            else:
                groups[-1].append(sentence)
                current_len = next_len

        return [" ".join(group) for group in groups if group]

    def chunk(self, documents: list[DocumentChunk]) -> list[DocumentChunk]:
        result_chunks: list[DocumentChunk] = []

        for doc in documents:
            if not doc.content.strip():
                continue

            sentences = _split_sentences(doc.content)
            sub_texts = self._group_sentences(sentences)
            if not sub_texts:
                continue

            for i, text in enumerate(sub_texts):
                child_id = stable_chunk_id(
                    doc.doc_id,
                    doc.chunk_type.value,
                    doc.page_number,
                    text,
                    x0=doc.bounding_box.x0 if doc.bounding_box else None,
                    y0=doc.bounding_box.y0 if doc.bounding_box else None,
                    x1=doc.bounding_box.x1 if doc.bounding_box else None,
                    y1=doc.bounding_box.y1 if doc.bounding_box else None,
                )
                child = doc.model_copy(
                    update={
                        "id": stable_split_chunk_id(child_id, i, chunker="semantic"),
                        "content": text,
                        "metadata": {
                            **doc.metadata,
                            "parent_chunk_id": doc.id,
                            "split_index": i,
                            "chunker": "semantic",
                        },
                    }
                )
                result_chunks.append(child)

        return result_chunks
