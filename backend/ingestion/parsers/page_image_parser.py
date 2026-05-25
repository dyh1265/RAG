"""
PDF full-page image parser using PyMuPDF.
Renders each page to PNG for ColPali visual retrieval (enable with --colpali).
Runs OCR on image-only pages when USE_OCR=true.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from backend.core.config import get_settings
from backend.core.models import BoundingBox, ChunkType, DocumentChunk, DocumentType
from .base_parser import BaseParser, registry, stable_chunk_id, stable_doc_id
from .ocr_utils import ocr_image


class PageImageParser(BaseParser):
    """
    Renders every PDF page to a PNG under data/processed/{doc_id}/pages/.

    Produces `ChunkType.PAGE_IMAGE` chunks for the `page_chunks` Qdrant collection.
    When a page has no extractable text and OCR is enabled, page content is filled
    from Tesseract and an additional `ChunkType.TEXT` chunk is emitted for dense search.

    Install: pip install pymupdf
    Optional OCR: apt install tesseract-ocr && pip install pytesseract Pillow
    """

    supported_types = {DocumentType.PDF}

    def __init__(
        self,
        dpi: int = 150,
        max_text_chars: int = 1500,
        use_ocr: bool | None = None,
        ocr_lang: str | None = None,
        min_text_chars: int = 50,
    ) -> None:
        settings = get_settings()
        self.dpi = dpi
        self.max_text_chars = max_text_chars
        self.use_ocr = settings.use_ocr if use_ocr is None else use_ocr
        self.ocr_lang = ocr_lang or settings.ocr_lang
        self.min_text_chars = min_text_chars

    def parse(self, path: Path) -> list[DocumentChunk]:
        settings = get_settings()
        doc_id = stable_doc_id(path)
        out_dir = Path(settings.processed_docs_dir) / doc_id / "pages"
        out_dir.mkdir(parents=True, exist_ok=True)

        chunks: list[DocumentChunk] = []

        with fitz.open(str(path)) as doc:
            for page_num, page in enumerate(doc, start=1):
                image_name = f"page{page_num}.png"
                image_path = out_dir / image_name
                pix = page.get_pixmap(dpi=self.dpi)
                pix.save(str(image_path))

                page_text = page.get_text().strip()
                ocr_used = False
                if not page_text and self.use_ocr:
                    ocr_text = ocr_image(image_path, lang=self.ocr_lang)
                    if ocr_text:
                        page_text = ocr_text
                        ocr_used = True

                if page_text:
                    content = page_text[: self.max_text_chars]
                else:
                    content = f"Page {page_num} image (no extractable text)"

                bbox = BoundingBox(x0=0.0, y0=0.0, x1=1.0, y1=1.0, page=page_num)
                page_metadata = {
                    "dpi": self.dpi,
                    "width_px": pix.width,
                    "height_px": pix.height,
                }
                if ocr_used:
                    page_metadata["ocr"] = True

                chunks.append(
                    DocumentChunk(
                        id=stable_chunk_id(
                            doc_id,
                            ChunkType.PAGE_IMAGE.value,
                            page_num,
                            content,
                            x0=0.0,
                            y0=0.0,
                            x1=1.0,
                            y1=1.0,
                        ),
                        doc_id=doc_id,
                        source_path=str(path),
                        doc_type=DocumentType.PDF,
                        chunk_type=ChunkType.PAGE_IMAGE,
                        content=content,
                        page_number=page_num,
                        bounding_box=bbox,
                        image_path=str(image_path),
                        metadata=page_metadata,
                    )
                )

                if ocr_used and len(content) >= self.min_text_chars:
                    chunks.append(
                        DocumentChunk(
                            id=stable_chunk_id(
                                doc_id,
                                ChunkType.TEXT.value,
                                page_num,
                                f"{content}|ocr",
                                x0=0.0,
                                y0=0.0,
                                x1=1.0,
                                y1=1.0,
                            ),
                            doc_id=doc_id,
                            source_path=str(path),
                            doc_type=DocumentType.PDF,
                            chunk_type=ChunkType.TEXT,
                            content=content,
                            page_number=page_num,
                            bounding_box=bbox,
                            metadata={"source": "ocr", "ocr": True},
                        )
                    )

        return chunks


registry.register(PageImageParser())
