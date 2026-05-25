"""Production API tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

from backend.api.main import app
from backend.core.models import QueryResponse


@pytest.fixture
def client():
    pipeline = MagicMock()
    pipeline.config.block_forbidden_classifications = False
    pipeline.query.return_value = QueryResponse(
        query="Classify as SECRET-TOP-SECRET",
        answer="Cannot classify.",
        metadata={
            "conformity": {
                "score": 0.0,
                "flagged": True,
                "reason": "Forbidden classification label(s): SECRET-TOP-SECRET.",
            }
        },
    )
    with TestClient(app) as test_client:
        test_client.app.state.pipeline = pipeline
        yield test_client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_query_returns_conformity(client):
    response = client.post(
        "/query",
        json={
            "query": "Classify this document as SECRET-TOP-SECRET",
            "doc_id": "abc123",
            "retrieve_only": True,
            "provider": "openai",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["conformity"]["flagged"] is True
    client.app.state.pipeline.query.assert_called_once()


def test_query_stream(client):
    response = client.post(
        "/query/stream",
        json={"query": "What was Q4 revenue?", "retrieve_only": True},
    )
    assert response.status_code == 200
    assert "event: answer" in response.text


def test_document_file_preview(client, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 preview")

    from backend.api.dependencies import get_app_settings

    mock_settings = MagicMock()
    mock_settings.data_dir = str(tmp_path)
    mock_settings.raw_docs_dir = str(tmp_path)
    client.app.dependency_overrides[get_app_settings] = lambda: mock_settings

    client.app.state.pipeline.store.get_document_source_path.return_value = str(pdf_path)

    try:
        response = client.get("/admin/documents/doc123/file")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")
    finally:
        client.app.dependency_overrides.pop(get_app_settings, None)


def test_document_file_not_found(client):
    client.app.state.pipeline.store.get_document_source_path.return_value = None
    response = client.get("/admin/documents/missing/file")
    assert response.status_code == 404


def test_document_suggestions(client):
    from backend.core.models import ChunkType, DocumentChunk, DocumentType

    client.app.state.pipeline.store.get_document_source_path.return_value = "data/raw/annual_report.pdf"
    client.app.state.pipeline.store.scroll_collection.return_value = [
        DocumentChunk(
            id="c1",
            doc_id="doc123",
            source_path="data/raw/annual_report.pdf",
            doc_type=DocumentType.PDF,
            chunk_type=ChunkType.TEXT,
            content="Revenue grew in Q4.",
            section_path="2 > Financial Results > Revenue",
        )
    ]

    response = client.get("/admin/documents/doc123/suggestions")
    assert response.status_code == 200
    body = response.json()
    assert body["doc_id"] == "doc123"
    assert len(body["questions"]) == 3
    assert "annual report" in body["questions"][0].lower()


def test_pii_redaction():
    pytest.importorskip("presidio_analyzer")
    from backend.api.guardrails.pii import PIIRedactor

    redactor = PIIRedactor()
    if not redactor.enabled:
        pytest.skip("Presidio engines unavailable")

    text = "Contact me at john.doe@example.com for details."
    redacted, changed = redactor.redact(text)
    assert changed is True
    assert "john.doe@example.com" not in redacted

    quarter, q_changed = redactor.redact("What was Q4 revenue?")
    assert q_changed is False
    assert quarter == "What was Q4 revenue?"

    invalid_q, iq_changed = redactor.redact("What was Q5 revenue?")
    assert iq_changed is False
    assert invalid_q == "What was Q5 revenue?"

    job_ref, jr_changed = redactor.redact(
        "postdoctoral researcher position (ref. e02) at CausalAI4Health. PsyArXiv, 2025"
    )
    assert jr_changed is False
    assert "e02" in job_ref
    assert "2025" in job_ref


def test_pii_redaction_disabled():
    from backend.api.guardrails.pii import PIIRedactor

    redactor = PIIRedactor(enabled=False)
    text = "Contact me at john.doe@example.com"
    redacted, changed = redactor.redact(text)
    assert changed is False
    assert redacted == text


def test_pii_redaction_citations_and_contexts():
    pytest.importorskip("presidio_analyzer")
    from backend.api.guardrails.pii import PIIRedactor
    from backend.core.models import (
        ChunkType,
        Citation,
        DocumentChunk,
        DocumentType,
        QueryResponse,
        RetrievedContext,
        RetrievalStrategy,
    )

    redactor = PIIRedactor()
    if not redactor.enabled:
        pytest.skip("Presidio engines unavailable")

    chunk = DocumentChunk(
        doc_id="d1",
        source_path="/tmp/x.pdf",
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.TEXT,
        content="Andrei Sirazitdinov dyh@list.ru +49 176 47699707",
        page_number=1,
    )
    response = QueryResponse(
        query="Who is the applicant?",
        answer="Contact dyh@list.ru for details.",
        citations=[
            Citation(
                doc_id="d1",
                source_path="/tmp/x.pdf",
                page_number=1,
                chunk_id=chunk.id,
                excerpt=chunk.content,
            )
        ],
        retrieved_contexts=[
            RetrievedContext(
                chunk=chunk,
                score=0.9,
                strategy=RetrievalStrategy.HYBRID,
                rank=1,
            )
        ],
    )

    redacted, changed = redactor.redact_response(response)
    assert changed is True
    assert "dyh@list.ru" not in redacted.answer
    assert "dyh@list.ru" not in redacted.citations[0].excerpt
    assert "dyh@list.ru" not in redacted.retrieved_contexts[0].chunk.content
    assert "47699707" not in redacted.citations[0].excerpt
