"""Run the retrieval eval over the golden set and emit a Markdown summary.

Designed for `$GITHUB_STEP_SUMMARY` so the scheduled RAG-eval workflow
publishes real benchmark numbers next to the green checkmark. Also works
locally; see ``--help``.

Usage:
    python scripts/run_eval_report.py                 # prints Markdown to stdout
    python scripts/run_eval_report.py -o bench.md     # writes to file
    GITHUB_STEP_SUMMARY=summary.md python scripts/run_eval_report.py
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.config import get_settings
from backend.core.models import QueryRequest
from backend.core.pipeline import PipelineConfig, RAGPipeline
from tests.eval.golden import load_golden_cases
from tests.eval.metrics import hit_at_k, latency_p95_ms, mean_metric, mrr, recall_at_k
from tests.eval.thresholds import eval_thresholds

SAMPLE_PDF = ROOT / "data" / "raw" / "sample_report.pdf"


def _build_pipeline() -> RAGPipeline:
    settings = get_settings()
    pipeline = RAGPipeline(
        PipelineConfig(
            use_hybrid=settings.use_hybrid,
            use_recursive_chunker=settings.use_recursive_chunker,
            use_semantic_chunker=settings.use_semantic_chunker,
            use_section_paths=settings.use_section_paths,
            use_context_enrichment=settings.use_context_enrichment,
            use_parent_expand=settings.use_parent_expand,
            use_flashrank=settings.use_flashrank,
            use_colpali=settings.use_colpali,
            use_taxonomy_validation=False,
            llm_provider="openai" if settings.openai_api_key else "ollama",
        ),
    )
    result = pipeline.ingest(SAMPLE_PDF)
    if result.chunk_count == 0:
        raise RuntimeError(f"Ingest produced no chunks: {result.errors}")
    return pipeline


def _score(pipeline: RAGPipeline, top_k: int) -> dict[str, float]:
    cases = load_golden_cases()
    recalls: list[float] = []
    hits: list[float] = []
    mrrs: list[float] = []
    latencies: list[float] = []

    started = time.perf_counter()
    for case in cases:
        request = QueryRequest(
            query=case.query,
            top_k=top_k,
            filters={"doc_id": case.doc_id},
        )
        response = pipeline.query(request, generate_answer=False)
        contexts = response.retrieved_contexts
        latencies.append(response.latency_ms or 0.0)
        recalls.append(recall_at_k(contexts, case.relevant_pages, k=5))
        hits.append(hit_at_k(contexts, case.relevant_pages, k=5))
        mrrs.append(mrr(contexts, case.relevant_pages))
    elapsed_s = time.perf_counter() - started

    warmed = latencies[1:] if len(latencies) > 1 else latencies

    return {
        "n_cases": float(len(cases)),
        "recall_at_5": mean_metric(recalls),
        "hit_at_5": mean_metric(hits),
        "mrr": mean_metric(mrrs),
        "retrieve_p95_ms": latency_p95_ms(warmed),
        "wall_clock_s": elapsed_s,
    }


def _render(scores: dict[str, float]) -> str:
    limits = eval_thresholds()
    rows = [
        ("Recall@5", scores["recall_at_5"], limits["recall_at_5"], "{:.3f}", "≥"),
        ("Hit@5", scores["hit_at_5"], limits["hit_at_5"], "{:.3f}", "≥"),
        ("MRR", scores["mrr"], limits["mrr"], "{:.3f}", "≥"),
        (
            "p95 retrieval latency (ms)",
            scores["retrieve_p95_ms"],
            limits["retrieval_latency_p95_ms"],
            "{:.0f}",
            "≤",
        ),
    ]
    lines = [
        "## DocuMind retrieval benchmarks",
        "",
        f"Golden cases: **{int(scores['n_cases'])}** · wall clock: **{scores['wall_clock_s']:.1f}s**",
        "",
        "| Metric | Result | CI threshold | Pass |",
        "|---|---|---|---|",
    ]
    for label, value, threshold, fmt, op in rows:
        passed = (value >= threshold) if op == "≥" else (value <= threshold)
        mark = "✅" if passed else "❌"
        lines.append(
            f"| {label} | {fmt.format(value)} | {op} {fmt.format(threshold)} | {mark} |"
        )
    lines.append("")
    lines.append(
        "_Thresholds come from `backend/core/config.py` (`EVAL_*`). "
        "Sample document: `data/raw/sample_report.pdf`._"
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Write the Markdown report here (default: stdout, plus $GITHUB_STEP_SUMMARY if set).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=int(os.getenv("EVAL_TOP_K", "10")),
        help="top_k for retrieval (default: 10 or $EVAL_TOP_K).",
    )
    args = parser.parse_args()

    if not SAMPLE_PDF.exists():
        print(
            f"sample_report.pdf missing at {SAMPLE_PDF}. "
            "Run `python scripts/generate_sample_report.py` first.",
            file=sys.stderr,
        )
        return 2

    pipeline = _build_pipeline()
    scores = _score(pipeline, top_k=args.top_k)
    report = _render(scores)

    print(report)

    targets: list[Path] = []
    if args.output:
        targets.append(args.output)
    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        targets.append(Path(step_summary))

    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
