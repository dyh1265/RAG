"""Tests for document and chunk fingerprinting."""

from __future__ import annotations


from phases.phase_03_scalable_ingestion.embedding.fingerprint import chunk_embed_key, doc_fingerprint
from shared.models import ChunkType, DocumentChunk, DocumentType


def test_doc_fingerprint_stable(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-test")
    assert doc_fingerprint(pdf) == doc_fingerprint(pdf)


def test_doc_fingerprint_changes_on_write(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"a")
    first = doc_fingerprint(pdf)
    pdf.write_bytes(b"b")
    assert doc_fingerprint(pdf) != first


def test_chunk_embed_key_includes_content():
    chunk = DocumentChunk(
        doc_id="d",
        source_path="/x.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.TEXT,
        content="hello world",
    )
    a = chunk_embed_key(chunk)
    chunk.content = "different"
    assert chunk_embed_key(chunk) != a
