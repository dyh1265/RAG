"""
PDF figure parser using PyMuPDF.
Crops embedded images, saves PNGs, and builds searchable text from nearby captions.
Optional OCR when pytesseract is installed.
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF

from shared.config import get_settings
from shared.models import BoundingBox, ChunkType, DocumentChunk, DocumentType
from .base_parser import BaseParser, registry, stable_chunk_id, stable_doc_id
from .ocr_utils import ocr_image

FIGURE_REF = re.compile(r"\bfigure\s+\d+", re.IGNORECASE)


def _find_captions(page: fitz.Page, image_rect: fitz.Rect, margin: float = 72) -> list[str]:
    """Collect caption-like text blocks near or referencing the figure."""
    expanded = fitz.Rect(
        image_rect.x0 - margin,
        image_rect.y0 - margin,
        image_rect.x1 + margin,
        image_rect.y1 + margin,
    )
    figure_first: list[str] = []
    nearby: list[str] = []
    for block in page.get_text("blocks", sort=True):
        if block[6] != 0:
            continue
        text = block[4].strip()
        if len(text) < 20:
            continue
        block_rect = fitz.Rect(block[:4])
        if FIGURE_REF.search(text):
            figure_first.append(text)
        elif expanded.intersects(block_rect):
            nearby.append(text)

    seen: set[str] = set()
    ordered: list[str] = []
    for text in figure_first + nearby:
        if text not in seen:
            seen.add(text)
            ordered.append(text)
    return ordered


class FigureParser(BaseParser):
    """
    Extracts embedded images from PDF pages as figure chunks.

    Each figure is cropped to PNG under data/processed/{doc_id}/figures/.
    Searchable `content` is built from on-page captions; optional OCR augments it.

    Install: pip install pymupdf Pillow
    Optional OCR: pip install pytesseract (+ Tesseract system binary)
    """

    supported_types = {DocumentType.PDF}

    def __init__(
        self,
        min_width: float = 80,
        min_height: float = 80,
        use_ocr: bool = False,
        caption_margin: float = 72,
    ) -> None:
        self.min_width = min_width
        self.min_height = min_height
        self.use_ocr = use_ocr
        self.caption_margin = caption_margin

    def parse(self, path: Path) -> list[DocumentChunk]:
        settings = get_settings()
        doc_id = stable_doc_id(path)
        out_dir = Path(settings.processed_docs_dir) / doc_id / "figures"
        out_dir.mkdir(parents=True, exist_ok=True)

        chunks: list[DocumentChunk] = []
        seen_xrefs: set[tuple[int, tuple[float, float, float, float]]] = set()

        with fitz.open(str(path)) as doc:
            for page_num, page in enumerate(doc, start=1):
                fig_idx = 0
                for img in page.get_images(full=True):
                    xref = img[0]
                    for rect in page.get_image_rects(xref):
                        if rect.width < self.min_width or rect.height < self.min_height:
                            continue
                        key = (xref, tuple(round(v, 1) for v in rect))
                        if key in seen_xrefs:
                            continue
                        seen_xrefs.add(key)

                        image_name = f"page{page_num}_fig{fig_idx}.png"
                        image_path = out_dir / image_name
                        pix = page.get_pixmap(clip=rect, dpi=150)
                        pix.save(str(image_path))

                        captions = _find_captions(page, rect, margin=self.caption_margin)
                        content_parts = list(captions)
                        if self.use_ocr:
                            ocr_text = ocr_image(image_path)
                            if ocr_text:
                                content_parts.append(f"OCR: {ocr_text}")
                        if not content_parts:
                            content_parts.append(f"Figure on page {page_num}")

                        content = "\n\n".join(content_parts)
                        page_rect = page.rect
                        bbox = BoundingBox(
                            x0=rect.x0 / page_rect.width,
                            y0=rect.y0 / page_rect.height,
                            x1=rect.x1 / page_rect.width,
                            y1=rect.y1 / page_rect.height,
                            page=page_num,
                        )

                        chunks.append(
                            DocumentChunk(
                                id=stable_chunk_id(
                                    doc_id,
                                    ChunkType.FIGURE.value,
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
                                chunk_type=ChunkType.FIGURE,
                                content=content,
                                page_number=page_num,
                                bounding_box=bbox,
                                image_path=str(image_path),
                                metadata={
                                    "figure_index": fig_idx,
                                    "image_xref": xref,
                                    "caption_count": len(captions),
                                },
                            )
                        )
                        fig_idx += 1

        return chunks


registry.register(FigureParser())
