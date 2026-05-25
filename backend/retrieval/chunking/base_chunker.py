"""
Abstract base chunker — all chunking strategies implement this interface.
A chunker takes a list of raw DocumentChunks (from a parser) and splits/reorganises
them into final indexable chunks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.core.models import DocumentChunk


class BaseChunker(ABC):
    """
    Abstract chunker.

    Chunkers sit between parsers and embedders.
    Input:  list of coarse DocumentChunks (e.g. full text blocks from PDFTextParser)
    Output: list of fine-grained DocumentChunks ready for embedding

    Subclasses
    ----------
    - RecursiveChunker      : fixed-size with overlap (baseline)
    - SemanticChunker       : split at semantic similarity drops
    - PropositionChunker    : LLM-based atomic fact extraction
    - HierarchicalChunker   : builds parent→child chunk tree
    - LateChunker           : embed full doc, then slice embeddings at boundaries
    """

    @abstractmethod
    def chunk(self, documents: list[DocumentChunk]) -> list[DocumentChunk]:
        """
        Split input documents into indexable chunks.

        Parameters
        ----------
        documents : list[DocumentChunk]
            Coarse chunks from a parser (e.g. one per page or one per text block).

        Returns
        -------
        list[DocumentChunk]
            Fine-grained chunks ready for embedding and indexing.
            Each returned chunk must preserve: doc_id, source_path, doc_type,
            page_number, and section_path from its parent.
        """

    def chunk_safe(
        self, documents: list[DocumentChunk]
    ) -> tuple[list[DocumentChunk], list[Exception]]:
        """Error-tolerant wrapper around `chunk()`."""
        try:
            return self.chunk(documents), []
        except Exception as exc:
            return [], [exc]
