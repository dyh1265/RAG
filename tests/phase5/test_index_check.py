"""Tests for Phase 5 index check."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from phases.phase_05_evaluation.index_check import (
    doc_is_indexed,
    ensure_docs_indexed,
    required_doc_paths,
)
from shared.models import EvalSample


def test_required_doc_paths_dedupes():
    samples = [
        EvalSample(id="a", question="q", ground_truth_answer="a", doc_path="data/raw/a.pdf"),
        EvalSample(id="b", question="q", ground_truth_answer="a", doc_path="data/raw/a.pdf"),
        EvalSample(id="c", question="q", ground_truth_answer="a", doc_path="data/raw/b.pdf"),
    ]
    paths = required_doc_paths(samples)
    assert paths == [Path("data/raw/a.pdf"), Path("data/raw/b.pdf")]


def test_doc_is_indexed_true_when_chunks_exist():
    pipeline = MagicMock()
    pipeline.store.scroll_collection.return_value = [{"id": "x"}]
    assert doc_is_indexed(pipeline, "doc-1") is True


def test_ensure_docs_indexed_warns_when_missing(monkeypatch, tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    samples = [
        EvalSample(id="x", question="q", ground_truth_answer="a", doc_path=str(pdf)),
    ]
    pipeline = MagicMock()
    monkeypatch.setattr(
        "phases.phase_05_evaluation.index_check.doc_is_indexed",
        lambda _p, _d: False,
    )
    warnings = ensure_docs_indexed(pipeline, samples, ingest_if_missing=False)
    assert any("Not indexed" in w for w in warnings)
    pipeline.ingest.assert_not_called()


def test_ensure_docs_indexed_ingests_when_flag_set(monkeypatch, tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    samples = [
        EvalSample(id="x", question="q", ground_truth_answer="a", doc_path=str(pdf)),
    ]
    pipeline = MagicMock()
    ingest_result = MagicMock(chunk_count=10, chunks_by_type={"text": 10})
    pipeline.ingest.return_value = ingest_result
    monkeypatch.setattr(
        "phases.phase_05_evaluation.index_check.doc_is_indexed",
        lambda _p, _d: False,
    )
    warnings = ensure_docs_indexed(pipeline, samples, ingest_if_missing=True)
    assert warnings == []
    pipeline.ingest.assert_called_once_with(pdf)
