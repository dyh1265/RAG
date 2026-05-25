"""Tests for long-document benchmark scoring."""

from __future__ import annotations

from pathlib import Path


from phases.phase_02_long_doc_retrieval.benchmark import (
    load_benchmark,
    page_hit,
    recall_at_k,
)
from tests.phase1.conftest import make_context


def test_load_benchmark():
    benchmark = load_benchmark(Path("data/benchmarks/long_doc_qa.json"))
    assert benchmark.doc_id == "809ce82615e07690"
    assert len(benchmark.samples) >= 5


def test_page_hit_within_tolerance():
    contexts = [make_context(chunk_id="a", page_number=84)]
    assert page_hit(contexts, [85], tolerance=3)
    assert not page_hit(contexts, [90], tolerance=3)
    assert not page_hit(contexts, [85], tolerance=0)


def test_recall_at_k_binary():
    hit = [make_context(chunk_id="a", page_number=733)]
    miss = [make_context(chunk_id="b", page_number=10)]
    assert recall_at_k(hit, [735], tolerance=3) == 1.0
    assert recall_at_k(miss, [735], tolerance=3) == 0.0
