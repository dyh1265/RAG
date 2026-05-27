"""
Abstract base parser — all document parsers implement this interface.

A parser takes a file path and returns a list of DocumentChunks.
Each chunk type (text, table, figure) has its own concrete parser,
but they all share this contract so downstream components are parser-agnostic.
"""

from __future__ import annotations

import hashlib
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from backend.core.models import DocumentChunk, DocumentType


def stable_doc_id(path: str | Path) -> str:
    """Deterministic document ID — stable across host/Docker path prefixes.

    Must work cross-platform: a Windows-style host path like
    ``C:\\Users\\me\\RAG\\data\\raw\\long_report.pdf`` and the corresponding
    container path ``/app/data/raw/long_report.pdf`` should hash identically
    regardless of whether this code runs on Windows, Linux, or macOS. We
    therefore split on both path separators ourselves instead of relying on
    ``Path.parts``, which treats backslashes as filename characters on POSIX.
    """
    raw = str(path).replace("\\", "/")
    parts = [p.lower() for p in raw.split("/") if p]
    # Drop a Windows drive letter like ``C:`` if present at the front.
    if parts and len(parts[0]) == 2 and parts[0].endswith(":"):
        parts = parts[1:]
    if "raw" in parts:
        idx = parts.index("raw")
        key = "/".join(parts[idx:])
    else:
        key = parts[-1] if parts else ""
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def stable_chunk_id(
    doc_id: str,
    chunk_type: str,
    page_number: int | None,
    content: str,
    *,
    x0: float | None = None,
    y0: float | None = None,
    x1: float | None = None,
    y1: float | None = None,
) -> str:
    """Deterministic chunk ID so re-ingest upserts instead of duplicating."""
    parts = [doc_id, chunk_type, str(page_number), content]
    if None not in (x0, y0, x1, y1):
        parts.extend(f"{v:.5f}" for v in (x0, y0, x1, y1))
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


def stable_split_chunk_id(base_id: str, split_index: int, *, chunker: str) -> str:
    """Qdrant-compatible deterministic UUID for split child chunks."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{base_id}:{chunker}:{split_index}"))


class BaseParser(ABC):
    """
    Abstract document parser.

    Subclass this and implement `parse()` to add support for a new file type
    or content region (text, table, figure).

    Example
    -------
    class MyPDFParser(BaseParser):
        supported_types = {DocumentType.PDF}

        def parse(self, path: Path) -> list[DocumentChunk]:
            ...
    """

    # Declare which DocumentType(s) this parser handles
    supported_types: set[DocumentType] = set()

    def can_parse(self, path: Path) -> bool:
        """Return True if this parser supports the given file."""
        ext_map: dict[str, DocumentType] = {
            ".pdf": DocumentType.PDF,
            ".docx": DocumentType.DOCX,
            ".doc": DocumentType.DOCX,
            ".txt": DocumentType.TXT,
            ".png": DocumentType.IMAGE,
            ".jpg": DocumentType.IMAGE,
            ".jpeg": DocumentType.IMAGE,
            ".html": DocumentType.HTML,
        }
        doc_type = ext_map.get(path.suffix.lower())
        return doc_type in self.supported_types

    @abstractmethod
    def parse(self, path: Path) -> list[DocumentChunk]:
        """
        Parse the document at `path` and return a flat list of DocumentChunks.

        Each chunk must have:
          - id            : unique, stable (uuid by default)
          - doc_id        : stable_doc_id(path) — same for all chunks from this file
          - source_path   : str(path)
          - doc_type      : the DocumentType of this file
          - chunk_type    : TEXT, TABLE, FIGURE, etc.
          - content       : plain-text representation (always required)
          - page_number   : if applicable
          - bounding_box  : if the chunk has a known location on the page
          - image_path    : path to cropped image, for figure/table chunks
        """

    def parse_safe(self, path: Path) -> tuple[list[DocumentChunk], list[Exception]]:
        """
        Wrapper around `parse()` that catches per-chunk errors gracefully.
        Returns (successful_chunks, errors).
        Useful in bulk ingestion where one bad document should not halt the pipeline.
        """
        try:
            chunks = self.parse(path)
            return chunks, []
        except Exception as exc:
            return [], [exc]


class ParserRegistry:
    """
    Registry of all available parsers.
    Call `get_parser(path)` to find the right parser for a file.
    """

    def __init__(self) -> None:
        self._parsers: list[BaseParser] = []

    def register(self, parser: BaseParser) -> None:
        self._parsers.append(parser)

    def get_parser(self, path: Path) -> BaseParser:
        for parser in self._parsers:
            if parser.can_parse(path):
                return parser
        raise ValueError(
            f"No registered parser supports '{path.suffix}'. "
            f"Register a parser for this file type first."
        )

    def get_all_parsers(self) -> list[BaseParser]:
        return list(self._parsers)


# Module-level singleton registry — import this in concrete parsers to register
registry = ParserRegistry()
