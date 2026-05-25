"""Phase 5 evaluation metrics — retrieval recall and lightweight answer quality."""

from __future__ import annotations

import re

from shared.config import get_settings
from shared.models import EvalSample, MetricScore, RetrievedContext

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 20]


def retrieval_page_recall(
    contexts: list[RetrievedContext],
    sample: EvalSample,
) -> MetricScore:
    """1.0 if any top-k chunk page is within tolerance of an expected page."""
    if not sample.expected_pages:
        return MetricScore(name="retrieval_page_recall", value=1.0, details={"skipped": True})

    pages = {ctx.chunk.page_number for ctx in contexts if ctx.chunk.page_number is not None}
    hit = any(
        abs(page - expected) <= sample.page_tolerance
        for page in pages
        for expected in sample.expected_pages
    )
    return MetricScore(
        name="retrieval_page_recall",
        value=1.0 if hit else 0.0,
        details={"retrieved_pages": sorted(pages), "expected_pages": sample.expected_pages},
    )


def retrieval_chunk_type_recall(
    contexts: list[RetrievedContext],
    sample: EvalSample,
) -> MetricScore:
    """1.0 if any retrieved chunk matches chunk_type_focus."""
    if sample.chunk_type_focus is None:
        return MetricScore(name="retrieval_chunk_type_recall", value=1.0, details={"skipped": True})

    focus = sample.chunk_type_focus
    types = {ctx.chunk.chunk_type for ctx in contexts}
    hit = focus in types
    return MetricScore(
        name="retrieval_chunk_type_recall",
        value=1.0 if hit else 0.0,
        details={"retrieved_types": [t.value for t in types], "expected": focus.value},
    )


def context_keyword_recall(contexts: list[str], ground_truth: str) -> MetricScore:
    """Fraction of ground-truth keywords found in any retrieved context."""
    gt_words = {w for w in re.findall(r"[a-z0-9]+", ground_truth.lower()) if len(w) > 3}
    if not gt_words:
        return MetricScore(name="context_keyword_recall", value=0.0, details={"skipped": True})

    corpus = " ".join(contexts).lower()
    found = sum(1 for w in gt_words if w in corpus)
    value = found / len(gt_words)
    return MetricScore(
        name="context_keyword_recall",
        value=value,
        details={"found": found, "total": len(gt_words)},
    )


def faithfulness_heuristic(answer: str, contexts: list[str]) -> MetricScore:
    """
    Fraction of answer sentences with a substantive overlap in retrieved context.

    Lightweight stand-in for RAGAS faithfulness when ragas is not installed.
    """
    if not answer.strip():
        return MetricScore(
            name="faithfulness",
            value=0.0,
            details={"skipped": True, "reason": "retrieve_only"},
        )

    sentences = _sentences(answer)
    if not sentences:
        return MetricScore(name="faithfulness", value=1.0 if contexts else 0.0)

    corpus = " ".join(contexts).lower()
    supported = 0
    for sentence in sentences:
        words = [w for w in re.findall(r"[a-z0-9]+", sentence.lower()) if len(w) > 3]
        if not words:
            continue
        hits = sum(1 for w in words if w in corpus)
        if hits / len(words) >= 0.4:
            supported += 1

    value = supported / len(sentences)
    return MetricScore(name="faithfulness", value=value, details={"supported": supported, "total": len(sentences)})


def answer_keyword_overlap(question: str, answer: str, ground_truth: str) -> MetricScore:
    """Share of ground-truth keywords (len>3) appearing in the generated answer."""
    gt_words = {w for w in re.findall(r"[a-z0-9]+", ground_truth.lower()) if len(w) > 3}
    if not gt_words:
        return MetricScore(name="answer_keyword_overlap", value=0.0)

    answer_words = set(re.findall(r"[a-z0-9]+", answer.lower()))
    overlap = len(gt_words & answer_words) / len(gt_words)
    return MetricScore(name="answer_keyword_overlap", value=overlap)


def compute_sample_metrics(
    sample: EvalSample,
    *,
    answer: str,
    contexts: list[RetrievedContext],
    context_texts: list[str],
    latency_ms: float,
    use_ragas: bool = False,
) -> list[MetricScore]:
    metrics = [
        retrieval_page_recall(contexts, sample),
        retrieval_chunk_type_recall(contexts, sample),
        context_keyword_recall(context_texts, sample.ground_truth_answer),
        faithfulness_heuristic(answer, context_texts),
        answer_keyword_overlap(sample.question, answer, sample.ground_truth_answer),
        MetricScore(name="latency_ms", value=latency_ms),
    ]

    if use_ragas and answer.strip():
        from phases.phase_05_evaluation.ragas_metrics import compute_ragas_metrics

        metrics.extend(
            compute_ragas_metrics(
                sample.question,
                answer,
                context_texts,
                ground_truth=sample.ground_truth_answer,
            )
        )
    return metrics


def _metric_value(metrics: list[MetricScore], name: str, default: float = 0.0) -> float:
    for m in metrics:
        if m.name == name:
            return m.value
    return default


def _metric_skipped(metrics: list[MetricScore], name: str) -> bool:
    for m in metrics:
        if m.name == name:
            return bool(m.details.get("skipped"))
    return False


def conformity_flag_match(sample: EvalSample, response_metadata: dict) -> MetricScore:
    """1.0 when conformity flagged state matches sample expectation."""
    if sample.expect_conformity_flagged is None:
        return MetricScore(name="conformity_flag_match", value=1.0, details={"skipped": True})

    conf = response_metadata.get("conformity", {})
    flagged = bool(conf.get("flagged"))
    expected = sample.expect_conformity_flagged
    match = flagged == expected
    return MetricScore(
        name="conformity_flag_match",
        value=1.0 if match else 0.0,
        details={"expected_flagged": expected, "actual_flagged": flagged, "reason": conf.get("reason")},
    )


def sample_passed(metrics: list[MetricScore], *, require_answer: bool = True) -> bool:
    settings = get_settings()

    if not _metric_skipped(metrics, "retrieval_page_recall"):
        if _metric_value(metrics, "retrieval_page_recall") < 1.0:
            return False

    if not _metric_skipped(metrics, "retrieval_chunk_type_recall"):
        if _metric_value(metrics, "retrieval_chunk_type_recall") < 1.0:
            return False

    if require_answer:
        # Prefer RAGAS faithfulness when present
        if any(m.name == "ragas_faithfulness" for m in metrics):
            if _metric_value(metrics, "ragas_faithfulness") < settings.eval_faithfulness_threshold:
                return False
        elif not _metric_skipped(metrics, "faithfulness"):
            if _metric_value(metrics, "faithfulness") < settings.eval_faithfulness_threshold:
                return False

    if not _metric_skipped(metrics, "conformity_flag_match"):
        if _metric_value(metrics, "conformity_flag_match") < 1.0:
            return False

    return True
