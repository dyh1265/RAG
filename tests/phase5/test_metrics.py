"""Tests for Phase 5 evaluation metrics."""

from __future__ import annotations

from phases.phase_05_evaluation.metrics import (
    answer_keyword_overlap,
    context_keyword_recall,
    faithfulness_heuristic,
    retrieval_page_recall,
    sample_passed,
)
from shared.models import EvalSample, MetricScore
from tests.phase1.conftest import make_context


def test_retrieval_page_recall_hit():
    sample = EvalSample(
        id="x",
        question="q",
        ground_truth_answer="a",
        expected_pages=[85],
    )
    contexts = [make_context(page_number=84)]
    metric = retrieval_page_recall(contexts, sample)
    assert metric.value == 1.0


def test_faithfulness_heuristic_supported_sentence():
    answer = "Q4 2024 revenue was $54.6M with operating margin of 22.8%."
    contexts = ["Q4 2024 | 54.6 | 17.9% | 22.8% operating margin in the table."]
    metric = faithfulness_heuristic(answer, contexts)
    assert metric.value > 0.5


def test_answer_keyword_overlap():
    metric = answer_keyword_overlap(
        "q",
        "Agile releases every two or three weeks to customers.",
        "New releases every two or three weeks.",
    )
    assert metric.value > 0.5


def test_context_keyword_recall():
    contexts = ["Agile methods release every two or three weeks to customers."]
    metric = context_keyword_recall(contexts, "New releases every two or three weeks.")
    assert metric.value > 0.5


def test_faithfulness_skipped_when_no_answer():
    metric = faithfulness_heuristic("", ["some context"])
    assert metric.details.get("skipped") is True


def test_sample_passed_retrieval_only():
    metrics = [
        MetricScore(name="retrieval_page_recall", value=1.0, details={}),
        MetricScore(name="retrieval_chunk_type_recall", value=1.0, details={"skipped": True}),
        MetricScore(name="faithfulness", value=0.0),
        MetricScore(name="latency_ms", value=5000),
    ]
    assert sample_passed(metrics, require_answer=False)
    assert not sample_passed(metrics, require_answer=True)
