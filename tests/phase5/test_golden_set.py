"""Tests for golden Q&A benchmark file."""

from __future__ import annotations

from pathlib import Path

from phases.phase_05_evaluation.run_full_eval import load_golden_set


def test_golden_set_loads():
    samples = load_golden_set(Path("data/benchmarks/golden_qa.json"))
    assert len(samples) >= 17
    tags = {tag for s in samples for tag in s.tags}
    assert "long-doc" in tags
    assert "table" in tags
    assert "figure" in tags


def test_golden_samples_have_doc_paths():
    samples = load_golden_set(Path("data/benchmarks/golden_qa.json"))
    assert all(s.doc_path for s in samples)
