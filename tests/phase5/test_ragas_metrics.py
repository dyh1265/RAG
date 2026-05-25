"""Tests for optional RAGAS integration."""

from __future__ import annotations

from phases.phase_05_evaluation.ragas_metrics import compute_ragas_metrics, ragas_available


def test_ragas_returns_empty_without_answer():
    assert compute_ragas_metrics("q", "", ["ctx"]) == []


def test_ragas_available_is_bool():
    assert isinstance(ragas_available(), bool)
