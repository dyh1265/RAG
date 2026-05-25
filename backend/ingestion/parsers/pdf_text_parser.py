"""
PDF text parser using PyMuPDF (fitz).
Extracts text blocks with page coordinates, preserving reading order.
"""

from __future__ import annotations

from pathlib import Path

from backend.core.models import BoundingBox, ChunkType, DocumentChunk, DocumentType
from .base_parser import BaseParser, registry, stable_chunk_id, stable_doc_id


class PDFTextParser(BaseParser):
    """
    Extracts text blocks from a PDF, one DocumentChunk per block.
    Blocks are already in reading order (top-to-bottom, left-to-right).

    Install: pip install pymupdf
    """

    supported_types = {DocumentType.PDF}

    def __init__(self, min_block_chars: int = 50) -> None:
        """
        Parameters
        ----------
        min_block_chars : int
            Skip text blocks shorter than this — avoids indexing page numbers,
            headers/footers, and other noise.
        """
        self.min_block_chars = min_block_chars

    def parse(self, path: Path) -> list[DocumentChunk]:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("Install PyMuPDF: pip install pymupdf")

        doc_id = stable_doc_id(path)
        chunks: list[DocumentChunk] = []

        with fitz.open(str(path)) as doc:
            for page_num, page in enumerate(doc, start=1):
                page_rect = page.rect
                # blocks: (x0, y0, x1, y1, text, block_no, block_type)
                for block in page.get_text("blocks", sort=True):
                    x0, y0, x1, y1, text, _, block_type = block
                    if block_type != 0:  # 0 = text, 1 = image
                        continue
                    text = text.strip()
                    if len(text) < self.min_block_chars:
                        continue

                    # Normalise bounding box to [0,1]
                    bbox = BoundingBox(
                        x0=x0 / page_rect.width,
                        y0=y0 / page_rect.height,
                        x1=x1 / page_rect.width,
                        y1=y1 / page_rect.height,
                        page=page_num,
                    )

                    chunks.append(DocumentChunk(
                        id=stable_chunk_id(
                            doc_id,
                            ChunkType.TEXT.value,
                            page_num,
                            text,
                            x0=bbox.x0,
                            y0=bbox.y0,
                            x1=bbox.x1,
                            y1=bbox.y1,
                        ),
                        doc_id=doc_id,
                        source_path=str(path),
                        doc_type=DocumentType.PDF,
                        chunk_type=ChunkType.TEXT,
                        content=text,
                        page_number=page_num,
                        bounding_box=bbox,
                    ))

        return chunks


# Auto-register when this module is imported
registry.register(PDFTextParser())
