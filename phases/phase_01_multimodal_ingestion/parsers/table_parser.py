"""
PDF table parser using pdfplumber.
Extracts structured tables as DocumentChunks with chunk_type=TABLE.
"""

from __future__ import annotations

from pathlib import Path

from shared.models import BoundingBox, ChunkType, DocumentChunk, DocumentType
from .base_parser import BaseParser, registry, stable_chunk_id, stable_doc_id


def format_table(rows: list[list[str | None]]) -> str:
    """Convert extracted table rows to a pipe-separated plain-text representation."""
    cleaned = [[(cell or "").strip() for cell in row] for row in rows]
    cleaned = [row for row in cleaned if any(cell for cell in row)]
    if len(cleaned) < 2:
        return ""
    return "\n".join(" | ".join(row) for row in cleaned)


class TableParser(BaseParser):
    """
    Extracts tables from PDF pages using pdfplumber line detection.

    Install: pip install pdfplumber
    """

    supported_types = {DocumentType.PDF}

    def __init__(self, min_rows: int = 2, min_cols: int = 2, min_chars: int = 50) -> None:
        self.min_rows = min_rows
        self.min_cols = min_cols
        self.min_chars = min_chars

    def parse(self, path: Path) -> list[DocumentChunk]:
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("Install pdfplumber: pip install pdfplumber")

        doc_id = stable_doc_id(path)
        chunks: list[DocumentChunk] = []

        with pdfplumber.open(str(path)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                for table_idx, table in enumerate(page.find_tables()):
                    rows = table.extract()
                    if not rows:
                        continue

                    max_cols = max(len(row) for row in rows)
                    if max_cols < self.min_cols or len(rows) < self.min_rows:
                        continue

                    content = format_table(rows)
                    if len(content) < self.min_chars:
                        continue

                    x0, top, x1, bottom = table.bbox
                    bbox = BoundingBox(
                        x0=x0 / page.width,
                        y0=top / page.height,
                        x1=x1 / page.width,
                        y1=bottom / page.height,
                        page=page_num,
                    )

                    chunks.append(
                        DocumentChunk(
                            id=stable_chunk_id(
                                doc_id,
                                ChunkType.TABLE.value,
                                page_num,
                                content,
                                x0=bbox.x0,
                                y0=bbox.y0,
                                x1=bbox.x1,
                                y1=bbox.y1,
                            ),
                            doc_id=doc_id,
                            source_path=str(path),
                            doc_type=DocumentType.PDF,
                            chunk_type=ChunkType.TABLE,
                            content=content,
                            page_number=page_num,
                            bounding_box=bbox,
                            metadata={"table_index": table_idx, "row_count": len(rows)},
                        )
                    )

        return chunks


registry.register(TableParser())
