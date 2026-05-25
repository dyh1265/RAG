"""
Orchestrates multiple parsers for a single document.
Each parser extracts a different content type (text, tables, figures).
"""

from __future__ import annotations

from pathlib import Path

from backend.core.models import DocumentChunk
from backend.ingestion.parsers.base_parser import BaseParser


class IngestionPipeline:
    """
    Run all registered parsers that support a file and merge their chunks.

    Example
    -------
    pipeline = IngestionPipeline([PDFTextParser(), TableParser()])
    chunks, errors = pipeline.parse_safe(path)
    """

    def __init__(self, parsers: list[BaseParser]) -> None:
        self.parsers = parsers

    def parse(self, path: Path) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for parser in self.parsers:
            if parser.can_parse(path):
                chunks.extend(parser.parse(path))
        return chunks

    def parse_safe(self, path: Path) -> tuple[list[DocumentChunk], list[Exception]]:
        chunks: list[DocumentChunk] = []
        errors: list[Exception] = []
        for parser in self.parsers:
            if parser.can_parse(path):
                parser_chunks, parser_errors = parser.parse_safe(path)
                chunks.extend(parser_chunks)
                errors.extend(parser_errors)
        return chunks, errors
