"""Assign section_path to text chunks from PDF heading font sizes."""

from __future__ import annotations

from pathlib import Path

from shared.models import ChunkType, DocumentChunk


def _extract_page_headings(path: Path) -> dict[int, list[tuple[float, str]]]:
    """Return normalized-y headings per page (y0 ascending)."""
    try:
        import fitz
    except ImportError:
        raise ImportError("Install PyMuPDF: pip install pymupdf") from None

    headings: dict[int, list[tuple[float, str]]] = {}
    with fitz.open(str(path)) as doc:
        for page_num, page in enumerate(doc, start=1):
            page_rect = page.rect
            page_height = page_rect.height or 1.0
            block_dict = page.get_text("dict")
            line_entries: list[tuple[float, float, str]] = []

            for block in block_dict.get("blocks", []):
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    if not spans:
                        continue
                    text = "".join(span.get("text", "") for span in spans).strip()
                    if not text:
                        continue
                    max_size = max(float(span.get("size", 0)) for span in spans)
                    y0 = float(line["bbox"][1]) / page_height
                    line_entries.append((max_size, y0, text))

            if not line_entries:
                continue

            body_size = sorted(size for size, _, _ in line_entries)[len(line_entries) // 2]
            threshold = max(body_size * 1.15, body_size + 1.0)
            page_headings = [
                (y0, text)
                for size, y0, text in line_entries
                if size >= threshold and len(text) <= 120
            ]
            headings[page_num] = sorted(page_headings, key=lambda item: item[0])

    return headings


def _section_for_y(headings: list[tuple[float, str]], y0: float) -> str | None:
    active = [text for y, text in headings if y <= y0 + 0.001]
    return active[-1] if active else None


def apply_section_paths(chunks: list[DocumentChunk], path: Path) -> list[DocumentChunk]:
    """Tag text/table chunks with the nearest heading above them on the same page."""
    if path.suffix.lower() != ".pdf":
        return chunks

    headings = _extract_page_headings(path)
    if not headings:
        return chunks

    updated: list[DocumentChunk] = []
    for chunk in chunks:
        if (
            chunk.chunk_type not in {ChunkType.TEXT, ChunkType.TABLE, ChunkType.HEADING}
            or chunk.page_number is None
            or chunk.bounding_box is None
        ):
            updated.append(chunk)
            continue

        page_headings = headings.get(chunk.page_number, [])
        section = _section_for_y(page_headings, chunk.bounding_box.y0)
        if section and section != chunk.section_path:
            chunk = chunk.model_copy(update={"section_path": section})
        updated.append(chunk)

    return updated
