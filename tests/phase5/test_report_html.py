"""Tests for Phase 5 HTML report rendering."""

from __future__ import annotations

import pytest

from shared.models import EvalResult, EvalRunReport, MetricScore


@pytest.fixture
def sample_report() -> EvalRunReport:
    return EvalRunReport(
        system_label="phase_02_test",
        num_samples=1,
        aggregate_metrics={
            "retrieval_page_recall": 1.0,
            "latency_ms": 120.0,
        },
        sample_results=[
            EvalResult(
                sample_id="sr-text-revenue",
                query="What was revenue?",
                generated_answer="",
                ground_truth_answer="$191.7M",
                retrieved_chunk_ids=["c1"],
                metrics=[
                    MetricScore(
                        name="retrieval_page_recall",
                        value=1.0,
                        details={"retrieved_pages": [1], "expected_pages": [1]},
                    ),
                    MetricScore(name="latency_ms", value=120.0),
                ],
                passed=True,
                latency_ms=120.0,
            )
        ],
    )


def test_render_html_report(sample_report):
    pytest.importorskip("jinja2")
    from phases.phase_05_evaluation.report_html import render_html_report

    html = render_html_report(sample_report)
    assert "phase_02_test" in html
    assert "sr-text-revenue" in html
    assert "100%" in html or "Pass rate" in html


def test_save_html_report(sample_report, tmp_path):
    pytest.importorskip("jinja2")
    from phases.phase_05_evaluation.report_html import save_html_report

    path = save_html_report(sample_report, tmp_path / "report.html")
    assert path.exists()
    assert "PASS" in path.read_text(encoding="utf-8")
