"""Tests for stable IDs and parser registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.ingestion.parsers.base_parser import (
    BaseParser,
    ParserRegistry,
    stable_chunk_id,
    stable_doc_id,
)
from backend.core.models import ChunkType, DocumentChunk, DocumentType


def test_stable_doc_id_is_deterministic():
    assert stable_doc_id("/data/report.pdf") == stable_doc_id("/data/report.pdf")
    assert stable_doc_id("/data/a.pdf") != stable_doc_id("/data/b.pdf")
    assert len(stable_doc_id("x")) == 16


def test_stable_doc_id_matches_across_docker_and_host_paths():
    host = stable_doc_id(r"C:\Users\me\RAG\data\raw\long_report.pdf")
    docker = stable_doc_id("/app/data/raw/long_report.pdf")
    relative = stable_doc_id("data/raw/long_report.pdf")
    assert host == docker == relative


def test_stable_chunk_id_is_deterministic():
    kwargs = dict(
        doc_id="doc1",
        chunk_type=ChunkType.TEXT.value,
        page_number=2,
        content="Hello",
    )
    assert stable_chunk_id(**kwargs) == stable_chunk_id(**kwargs)
    assert stable_chunk_id(**kwargs, x0=0.1, y0=0.2, x1=0.3, y1=0.4) != stable_chunk_id(**kwargs)


class _StubParser(BaseParser):
    supported_types = {DocumentType.PDF}

    def parse(self, path: Path) -> list[DocumentChunk]:
        return []


def test_parser_registry_resolves_by_extension():
    registry = ParserRegistry()
    registry.register(_StubParser())
    parser = registry.get_parser(Path("report.pdf"))
    assert isinstance(parser, _StubParser)


def test_parser_registry_raises_for_unknown_type():
    registry = ParserRegistry()
    registry.register(_StubParser())
    with pytest.raises(ValueError, match="No registered parser"):
        registry.get_parser(Path("report.xyz"))
