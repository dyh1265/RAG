"""Answer-quality eval: keyword coverage (offline) and optional Ragas (OpenAI)."""

from __future__ import annotations

import os

import pytest

from backend.core.config import get_settings
from backend.core.models import QueryRequest
from backend.core.pipeline import RAGPipeline
from tests.eval.golden import GoldenCase
from tests.eval.metrics import keyword_coverage, mean_metric
from tests.eval.thresholds import eval_thresholds

pytestmark = [pytest.mark.integration, pytest.mark.eval]


def _cases_with_phrases(cases: list[GoldenCase]) -> list[GoldenCase]:
    return [c for c in cases if c.key_phrases]


@pytest.mark.skipif(
    not get_settings().openai_api_key,
    reason="OPENAI_API_KEY required for full RAG answer generation",
)
def test_keyword_coverage_on_generated_answers(
    eval_pipeline: RAGPipeline,
    golden_cases: list[GoldenCase],
    eval_top_k: int,
) -> None:
    cases = _cases_with_phrases(golden_cases)
    limits = eval_thresholds()
    coverages: list[float] = []
    per_case: list[tuple[str, float, list[str]]] = []

    for case in cases:
        request = QueryRequest(
            query=case.query,
            top_k=eval_top_k,
            filters={"doc_id": case.doc_id},
        )
        response = eval_pipeline.query(request, generate_answer=True, provider="openai")
        coverage = keyword_coverage(response.answer, case.key_phrases)
        coverages.append(coverage)
        per_case.append((case.id, coverage, case.key_phrases))

    mean_coverage = mean_metric(coverages)
    if mean_coverage < limits["keyword_coverage"]:
        weak = [f"{cid}={cov:.2f}" for cid, cov, _ in per_case if cov < 1.0]
        detail = ", ".join(weak) if weak else "see per-case scores"
        pytest.fail(
            f"mean keyword coverage {mean_coverage:.3f} < {limits['keyword_coverage']}; "
            f"weak cases: {detail}"
        )


@pytest.mark.skipif(
    not get_settings().openai_api_key or os.getenv("RUN_RAGAS_EVAL") != "1",
    reason="Set OPENAI_API_KEY and RUN_RAGAS_EVAL=1 to run Ragas metrics",
)
def test_ragas_faithfulness_threshold(
    eval_pipeline: RAGPipeline,
    golden_cases: list[GoldenCase],
    eval_top_k: int,
) -> None:
    pytest.importorskip("ragas")
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import faithfulness

    limits = eval_thresholds()
    rows: list[dict[str, str | list[str]]] = []

    for case in _cases_with_phrases(golden_cases[:5]):
        request = QueryRequest(
            query=case.query,
            top_k=eval_top_k,
            filters={"doc_id": case.doc_id},
        )
        response = eval_pipeline.query(request, generate_answer=True, provider="openai")
        contexts = [ctx.chunk.enriched_content for ctx in response.retrieved_contexts]
        rows.append(
            {
                "question": case.query,
                "answer": response.answer,
                "contexts": contexts,
            }
        )

    dataset = Dataset.from_list(rows)
    result = evaluate(dataset, metrics=[faithfulness])
    score = float(result["faithfulness"])
    assert score >= limits["faithfulness"], (
        f"ragas faithfulness {score:.3f} < {limits['faithfulness']}"
    )
