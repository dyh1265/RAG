"""Optional RAGAS metrics — used when ragas + OpenAI are available."""

from __future__ import annotations

import asyncio

from shared.models import MetricScore


def ragas_available() -> bool:
    try:
        import ragas  # noqa: F401
        from ragas.dataset_schema import SingleTurnSample  # noqa: F401
        return True
    except ImportError:
        return False


async def _score_metrics_async(
    question: str,
    answer: str,
    contexts: list[str],
    *,
    ground_truth: str | None = None,
) -> list[MetricScore]:
    from ragas.dataset_schema import SingleTurnSample
    from ragas.llms import llm_factory
    from ragas.metrics import AnswerRelevancy, Faithfulness

    from shared.config import get_settings

    settings = get_settings()
    llm = llm_factory(
        "openai",
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )
    sample = SingleTurnSample(
        user_input=question,
        response=answer,
        retrieved_contexts=contexts,
        reference=ground_truth or "",
    )

    metrics_out: list[MetricScore] = []
    for metric_cls, name in (
        (Faithfulness, "ragas_faithfulness"),
        (AnswerRelevancy, "ragas_answer_relevancy"),
    ):
        try:
            scorer = metric_cls(llm=llm)
            score = await scorer.single_turn_ascore(sample)
            metrics_out.append(
                MetricScore(
                    name=name,
                    value=float(score),
                    details={"source": "ragas"},
                )
            )
        except Exception as exc:
            metrics_out.append(
                MetricScore(
                    name=f"{name}_error",
                    value=0.0,
                    details={"error": str(exc), "source": "ragas"},
                )
            )
    return metrics_out


def compute_ragas_metrics(
    question: str,
    answer: str,
    contexts: list[str],
    *,
    ground_truth: str | None = None,
) -> list[MetricScore]:
    """
    Compute RAGAS faithfulness and answer relevancy for one sample.

    Returns an empty list when ragas is not installed or scoring fails.
    """
    if not answer.strip() or not contexts:
        return []

    if not ragas_available():
        return []

    try:
        from shared.config import get_settings

        if not get_settings().openai_api_key:
            return []

        return asyncio.run(
            _score_metrics_async(
                question,
                answer,
                contexts,
                ground_truth=ground_truth,
            )
        )
    except Exception as exc:
        return [
            MetricScore(
                name="ragas_error",
                value=0.0,
                details={"error": str(exc)},
            )
        ]
