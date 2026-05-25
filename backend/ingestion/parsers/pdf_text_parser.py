"""
PDF text parser using PyMuPDF (fitz).
Extracts text blocks with page coordinates, preserving reading order.
Merges short pseudocode lines so algorithms are not dropped at ingest.
"""

from __future__ import annotations

from pathlib import Path

from backend.core.models import BoundingBox, ChunkType, DocumentChunk, DocumentType
from backend.core.text_heuristics import looks_like_algorithm_body
from .base_parser import BaseParser, registry, stable_chunk_id, stable_doc_id


def _merge_page_blocks(
    blocks: list[tuple[float, float, float, float, str]],
    *,
    min_block_chars: int,
) -> list[tuple[str, float, float, float, float]]:
    """
    Combine consecutive short or pseudocode blocks on one page into single chunks.

    PyMuPDF often emits each algorithm line as its own block (< min_block_chars).
    """
    merged: list[tuple[str, float, float, float, float]] = []
    buffer_lines: list[str] = []
    buf_x0 = buf_y0 = buf_x1 = buf_y1 = 0.0

    def flush() -> None:
        nonlocal buffer_lines, buf_x0, buf_y0, buf_x1, buf_y1
        if not buffer_lines:
            return
        text = "\n".join(buffer_lines).strip()
        if len(text) >= min_block_chars or looks_like_algorithm_body(text):
            merged.append((text, buf_x0, buf_y0, buf_x1, buf_y1))
        buffer_lines = []

    for x0, y0, x1, y1, text in blocks:
        text = text.strip()
        if not text:
            continue
        mergeable = len(text) < min_block_chars or looks_like_algorithm_body(text)
        if mergeable:
            if not buffer_lines:
                buf_x0, buf_y0, buf_x1, buf_y1 = x0, y0, x1, y1
            else:
                buf_x0 = min(buf_x0, x0)
                buf_y0 = min(buf_y0, y0)
                buf_x1 = max(buf_x1, x1)
                buf_y1 = max(buf_y1, y1)
            buffer_lines.append(text)
            continue
        flush()
        merged.append((text, x0, y0, x1, y1))

    flush()
    return merged


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
            Skip isolated text blocks shorter than this unless merged into
            a neighboring pseudocode / algorithm block.
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
                raw_blocks: list[tuple[float, float, float, float, str]] = []
                for block in page.get_text("blocks", sort=True):
                    x0, y0, x1, y1, text, _, block_type = block
                    if block_type != 0:
                        continue
                    text = text.strip()
                    if text:
                        raw_blocks.append((x0, y0, x1, y1, text))

                for text, x0, y0, x1, y1 in _merge_page_blocks(
                    raw_blocks,
                    min_block_chars=self.min_block_chars,
                ):
                    bbox = BoundingBox(
                        x0=x0 / page_rect.width,
                        y0=y0 / page_rect.height,
                        x1=x1 / page_rect.width,
                        y1=y1 / page_rect.height,
                        page=page_num,
                    )
                    chunks.append(
                        DocumentChunk(
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
                        )
                    )

        return chunks


registry.register(PDFTextParser())
