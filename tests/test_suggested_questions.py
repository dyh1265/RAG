"""Tests for document-specific starter question generation."""

from shared.models import ChunkType, DocumentChunk, DocumentType
from shared.suggested_questions import build_suggested_questions, doc_title_from_name


def _chunk(
    *,
    section_path: str | None = None,
    chunk_type: ChunkType = ChunkType.TEXT,
) -> DocumentChunk:
    return DocumentChunk(
        id="c1",
        doc_id="doc1",
        source_path="data/raw/report.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=chunk_type,
        content="Sample content for testing.",
        section_path=section_path,
    )


def test_doc_title_from_name():
    assert doc_title_from_name("agile_learning_guide.pdf") == "agile learning guide"


def test_build_suggested_questions_uses_sections():
    chunks = [
        _chunk(section_path="1 > Introduction"),
        _chunk(section_path="2 > Financial Results > Revenue"),
        _chunk(section_path="2 > Financial Results > Revenue"),
    ]
    questions = build_suggested_questions(doc_name="annual_report.pdf", chunks=chunks)
    assert len(questions) == 3
    assert "annual report" in questions[0]
    assert "Introduction" in questions[1]
    assert "Revenue" in questions[2]


def test_build_suggested_questions_table_focus():
    chunks = [_chunk(chunk_type=ChunkType.TABLE)]
    questions = build_suggested_questions(doc_name="metrics.pdf", chunks=chunks)
    assert any("tables" in q.lower() for q in questions)
