"""Long-document retrieval benchmark helpers and exit-test scoring."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from shared.models import RetrievedContext

DEFAULT_BENCHMARK_PATH = Path("data/benchmarks/long_doc_qa.json")


class LongDocSample(BaseModel):
    id: str
    question: str
    expected_pages: list[int]
    page_tolerance: int = 3
    tags: list[str] = Field(default_factory=list)


class LongDocBenchmark(BaseModel):
    doc_path: str
    doc_id: str
    samples: list[LongDocSample]


def load_benchmark(path: str | Path | None = None) -> LongDocBenchmark:
    benchmark_path = Path(path or DEFAULT_BENCHMARK_PATH)
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    return LongDocBenchmark.model_validate(data)


def retrieved_pages(contexts: list[RetrievedContext]) -> set[int]:
    return {ctx.chunk.page_number for ctx in contexts if ctx.chunk.page_number is not None}


def page_hit(
    contexts: list[RetrievedContext],
    expected_pages: list[int],
    *,
    tolerance: int = 3,
) -> bool:
    """True when any retrieved page is within tolerance of an expected page."""
    pages = retrieved_pages(contexts)
    if not pages or not expected_pages:
        return False
    return any(
        abs(page - expected) <= tolerance
        for page in pages
        for expected in expected_pages
    )


def recall_at_k(
    contexts: list[RetrievedContext],
    expected_pages: list[int],
    *,
    tolerance: int = 3,
) -> float:
    """1.0 if any top-k hit matches an expected page, else 0.0."""
    return 1.0 if page_hit(contexts, expected_pages, tolerance=tolerance) else 0.0


def evaluate_samples(
    results: dict[str, list[RetrievedContext]],
    benchmark: LongDocBenchmark,
) -> tuple[float, list[tuple[LongDocSample, bool]]]:
    """Return mean page recall and per-sample pass/fail."""
    per_sample: list[tuple[LongDocSample, bool]] = []
    for sample in benchmark.samples:
        contexts = results.get(sample.question, [])
        passed = page_hit(
            contexts,
            sample.expected_pages,
            tolerance=sample.page_tolerance,
        )
        per_sample.append((sample, passed))

    if not per_sample:
        return 0.0, per_sample

    mean_recall = sum(1.0 if passed else 0.0 for _, passed in per_sample) / len(per_sample)
    return mean_recall, per_sample
