"""
Recursive character text splitter chunker (baseline strategy).
Uses LangChain's RecursiveCharacterTextSplitter under the hood.

This is the simplest chunking strategy — start here and compare against
more sophisticated approaches (semantic, proposition, hierarchical).
"""

from __future__ import annotations

from shared.config import get_settings
from shared.models import DocumentChunk
from phases.phase_01_multimodal_ingestion.parsers.base_parser import stable_chunk_id, stable_split_chunk_id
from .base_chunker import BaseChunker


class RecursiveChunker(BaseChunker):
    """
    Splits text by trying separators in order: paragraph → sentence → word → character.
    Produces overlapping chunks to avoid cutting context at boundaries.

    Install: pip install langchain-text-splitters tiktoken
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        separators: list[str] | None = None,
    ) -> None:
        settings = get_settings()
        self.chunk_size = chunk_size or settings.max_chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def chunk(self, documents: list[DocumentChunk]) -> list[DocumentChunk]:
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except ImportError:
            raise ImportError(
                "Install langchain text splitters: pip install langchain-text-splitters tiktoken"
            )

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators,
            length_function=len,
        )

        result_chunks: list[DocumentChunk] = []
        for doc in documents:
            if not doc.content.strip():
                continue

            sub_texts = splitter.split_text(doc.content)
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
                        "id": stable_split_chunk_id(child_id, i, chunker="recursive"),
                        "content": text,
                        "metadata": {
                            **doc.metadata,
                            "parent_chunk_id": doc.id,
                            "split_index": i,
                            "chunker": "recursive",
                        },
                    }
                )
                result_chunks.append(child)

        return result_chunks
