"""
Shared pytest fixtures for all phases.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from phases._legacy import install_legacy_imports
from shared.models import ChunkType, DocumentChunk, DocumentType

install_legacy_imports()


@pytest.fixture
def sample_pdf_path(tmp_path: Path) -> Path:
    """
    Returns the path to a minimal real PDF for integration tests.
    If you have a sample PDF in data/raw/, swap this path in.
    """
    # For now points to the placeholder location
    target = Path("data/raw/sample_report.pdf")
    if target.exists():
        return target
    pytest.skip("No sample PDF found at data/raw/sample_report.pdf")


@pytest.fixture
def sample_text_chunk() -> DocumentChunk:
    return DocumentChunk(
        id=str(uuid4()),
        doc_id="test_doc_001",
        source_path="data/raw/test.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.TEXT,
        content="Revenue increased by 15% year-over-year driven by strong performance in the cloud segment.",
        page_number=1,
        section_path="2 > Financial Results > Revenue",
    )


@pytest.fixture
def sample_chunks(sample_text_chunk: DocumentChunk) -> list[DocumentChunk]:
    """A small batch of chunks for testing embedders and retrievers."""
    base = sample_text_chunk
    return [
        base,
        base.model_copy(update={
            "id": str(uuid4()),
            "content": "Operating expenses rose modestly, maintaining healthy margins.",
            "page_number": 2,
        }),
        base.model_copy(update={
            "id": str(uuid4()),
            "content": "The board approved a new share buyback programme of $500 million.",
            "page_number": 3,
        }),
    ]
