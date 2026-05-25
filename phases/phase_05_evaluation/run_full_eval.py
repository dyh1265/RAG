"""
Full evaluation runner — golden Q&A set against RAGPipeline.

Usage
-----
# Retrieval-only (no LLM, fast CI):
python phases/phase_05_evaluation/run_full_eval.py --system phase_02 --retrieve-only \\
    --hybrid --recursive-chunk --tag long-doc --ingest-if-missing

# Full eval with OpenAI answers:
python phases/phase_05_evaluation/run_full_eval.py --system phase_02 --provider openai \\
    --hybrid --recursive-chunk --save-baseline --ragas

Install: pip install -e ".[phase5]"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from phases.phase_01_multimodal_ingestion.parsers.base_parser import stable_doc_id
from phases.phase_05_evaluation.index_check import ensure_docs_indexed
from phases.phase_05_evaluation.metrics import compute_sample_metrics, conformity_flag_match, sample_passed
from phases.phase_05_evaluation.report_html import save_html_report
from shared.config import get_settings
from shared.models import EvalResult, EvalRunReport, EvalSample, MetricScore, QueryRequest, QueryResponse
from shared.pipeline import PipelineConfig, RAGPipeline

REPORTS_DIR = Path("phases/phase_05_evaluation/reports")
BASELINE_DIR = Path("phases/phase_05_evaluation/baselines")


def load_golden_set(path: Path) -> list[EvalSample]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [EvalSample(**item) for item in data]


def get_git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:
        return None


def _doc_id_for_sample(sample: EvalSample) -> str | None:
    if sample.doc_path:
        return stable_doc_id(sample.doc_path)
    if sample.ground_truth_doc_ids:
        return sample.ground_truth_doc_ids[0]
    return None


def call_system(
    sample: EvalSample,
    pipeline: RAGPipeline,
    *,
    generate_answer: bool = True,
    provider: str | None = None,
) -> QueryResponse:
    """Run one golden sample through RAGPipeline."""
    doc_id = _doc_id_for_sample(sample)
    filters = {"doc_id": doc_id} if doc_id else {}
    request = QueryRequest(
        query=sample.question,
        top_k=sample.top_k,
        filters=filters,
    )
    return pipeline.query(
        request,
        generate_answer=generate_answer,
        provider=provider,
    )


def _format_retrieval(metrics: list[MetricScore]) -> str:
    for m in metrics:
        if m.name == "retrieval_page_recall" and not m.details.get("skipped"):
            pages = m.details.get("retrieved_pages", [])
            expected = m.details.get("expected_pages", [])
            hit = "✓" if m.value >= 1.0 else "✗"
            return f"{hit} pages {pages} (want ~{expected})"
        if m.name == "retrieval_chunk_type_recall" and not m.details.get("skipped"):
            got = m.details.get("retrieved_types", [])
            want = m.details.get("expected", "?")
            hit = "✓" if m.value >= 1.0 else "✗"
            return f"{hit} types {got} (want {want})"
    return "—"


def run_eval(
    samples: list[EvalSample],
    system_label: str,
    pipeline: RAGPipeline,
    *,
    generate_answer: bool = True,
    provider: str | None = None,
    use_ragas: bool = False,
    no_fail_on_error: bool = False,
) -> EvalRunReport:
    results: list[EvalResult] = []
    total = len(samples)

    for idx, sample in enumerate(samples, start=1):
        print(f"[eval] ({idx}/{total}) {sample.id} …", flush=True)
        t0 = time.perf_counter()
        try:
            response = call_system(
                sample,
                pipeline,
                generate_answer=generate_answer,
                provider=provider,
            )
            latency_ms = (time.perf_counter() - t0) * 1000

            context_texts = [ctx.chunk.content for ctx in response.retrieved_contexts]
            chunk_ids = [ctx.chunk.id for ctx in response.retrieved_contexts]
            metrics = compute_sample_metrics(
                sample,
                answer=response.answer,
                contexts=response.retrieved_contexts,
                context_texts=context_texts,
                latency_ms=latency_ms,
                use_ragas=use_ragas,
            )
            metrics.append(conformity_flag_match(sample, response.metadata))
            passed = sample_passed(metrics, require_answer=generate_answer)

            results.append(
                EvalResult(
                    sample_id=sample.id,
                    query=sample.question,
                    generated_answer=response.answer,
                    ground_truth_answer=sample.ground_truth_answer,
                    retrieved_chunk_ids=chunk_ids,
                    metrics=metrics,
                    passed=passed,
                    latency_ms=latency_ms,
                )
            )
            status = "PASS" if passed else "FAIL"
            print(f"       → {status} · {_format_retrieval(metrics)} · {latency_ms:.0f}ms", flush=True)
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000
            err_msg = f"{type(exc).__name__}: {exc}"
            print(f"       → ERROR · {err_msg}", flush=True)
            if not no_fail_on_error:
                raise
            results.append(
                EvalResult(
                    sample_id=sample.id,
                    query=sample.question,
                    generated_answer="",
                    ground_truth_answer=sample.ground_truth_answer,
                    retrieved_chunk_ids=[],
                    metrics=[
                        MetricScore(name="latency_ms", value=latency_ms),
                        MetricScore(name="error", value=0.0, details={"message": err_msg}),
                    ],
                    passed=False,
                    latency_ms=latency_ms,
                )
            )
            traceback.print_exc()

    all_metric_names = {m.name for r in results for m in r.metrics}
    aggregate: dict[str, float] = {}
    for name in all_metric_names:
        if name.endswith("_error") or name == "error":
            continue
        vals = [m.value for r in results for m in r.metrics if m.name == name]
        aggregate[name] = sum(vals) / len(vals) if vals else 0.0

    report = EvalRunReport(
        system_label=system_label,
        git_commit=get_git_commit(),
        num_samples=len(results),
        aggregate_metrics=aggregate,
        sample_results=results,
    )
    report.regression_alerts = check_regression(report)
    return report


def check_regression(report: EvalRunReport) -> list[str]:
    settings = get_settings()
    tolerance = settings.eval_regression_tolerance

    baseline_path = BASELINE_DIR / f"{report.system_label}_baseline.json"
    if not baseline_path.exists():
        return []

    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)

    alerts = []
    for metric, current_val in report.aggregate_metrics.items():
        if metric == "latency_ms":
            continue
        baseline_val = baseline.get(metric)
        if baseline_val is None or baseline_val == 0:
            continue
        drop = (baseline_val - current_val) / baseline_val
        if drop > tolerance:
            alerts.append(
                f"REGRESSION: {metric} dropped {drop:.1%} "
                f"(baseline={baseline_val:.3f}, current={current_val:.3f})"
            )
    return alerts


def filter_samples(samples: list[EvalSample], tag: str | None) -> list[EvalSample]:
    if not tag:
        return samples
    return [s for s in samples if tag in s.tags]


def save_report(report: EvalRunReport) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = REPORTS_DIR / f"{report.system_label}_{ts}.json"
    html_path = REPORTS_DIR / f"{report.system_label}_{ts}.html"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    save_html_report(report, html_path)
    return json_path, html_path


def _print_failures(report: EvalRunReport) -> None:
    failed = [r for r in report.sample_results if not r.passed]
    if not failed:
        return
    print(f"\n[eval] Failed samples ({len(failed)}):")
    for r in failed:
        print(f"  - {r.sample_id}: {_format_retrieval(r.metrics)}")
        for m in r.metrics:
            if m.name.endswith("_error") or m.name == "error":
                print(f"      {m.name}: {m.details.get('error') or m.details.get('message')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAG golden-set evaluation")
    parser.add_argument("--system", required=True, help="System label (e.g. phase_02)")
    parser.add_argument("--golden-set", default="data/benchmarks/golden_qa.json")
    parser.add_argument("--tag", help="Run only samples with this tag (e.g. long-doc, table)")
    parser.add_argument("--retrieve-only", action="store_true", help="Skip LLM answer generation")
    parser.add_argument("--provider", choices=["ollama", "openai"], default="openai")
    parser.add_argument("--hybrid", action="store_true")
    parser.add_argument("--recursive-chunk", action="store_true")
    parser.add_argument("--semantic-chunk", action="store_true")
    parser.add_argument("--ingest-if-missing", action="store_true", help="Ingest PDFs not yet in Qdrant")
    parser.add_argument("--ragas", action="store_true", help="Add RAGAS faithfulness/relevancy (needs OpenAI)")
    parser.add_argument("--save-baseline", action="store_true")
    parser.add_argument("--fail-on-regression", action="store_true")
    parser.add_argument("--allow-partial", action="store_true", help="Exit 0 even if some samples fail")
    parser.add_argument("--no-fail-on-error", action="store_true", help="Continue when a sample raises")
    args = parser.parse_args()

    settings = get_settings()
    golden_path = Path(args.golden_set)
    if not golden_path.exists():
        raise FileNotFoundError(f"Golden set not found: {golden_path}")

    samples = filter_samples(load_golden_set(golden_path), args.tag)
    if not samples:
        raise SystemExit(f"No samples matched tag={args.tag!r}")
    print(f"[eval] Loaded {len(samples)} samples from {golden_path}")

    pipeline = RAGPipeline(
        PipelineConfig(
            use_hybrid=args.hybrid or settings.use_hybrid,
            use_recursive_chunker=args.recursive_chunk or settings.use_recursive_chunker,
            use_semantic_chunker=args.semantic_chunk or settings.use_semantic_chunker,
            llm_provider=args.provider,
        )
    )
    pipeline.preload_models()

    index_warnings = ensure_docs_indexed(
        pipeline,
        samples,
        ingest_if_missing=args.ingest_if_missing,
    )
    if index_warnings:
        print("\n[eval] Index warnings:")
        for w in index_warnings:
            print(f"  - {w}")
        raise SystemExit(1)

    report = run_eval(
        samples,
        system_label=args.system,
        pipeline=pipeline,
        generate_answer=not args.retrieve_only,
        provider=args.provider,
        use_ragas=args.ragas,
        no_fail_on_error=args.no_fail_on_error,
    )

    passed = sum(1 for r in report.sample_results if r.passed)
    pass_rate = passed / report.num_samples if report.num_samples else 0.0
    print(f"\n[eval] Results for '{report.system_label}' — {passed}/{report.num_samples} passed ({pass_rate:.0%})")
    for metric, value in sorted(report.aggregate_metrics.items()):
        print(f"       {metric}: {value:.3f}")

    _print_failures(report)

    if report.regression_alerts:
        print("\n[ALERT] Regressions detected:")
        for alert in report.regression_alerts:
            print(f"  - {alert}")

    json_path, html_path = save_report(report)
    print(f"[eval] JSON report: {json_path}")
    print(f"[eval] HTML report: {html_path}")

    if args.save_baseline:
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        baseline_path = BASELINE_DIR / f"{report.system_label}_baseline.json"
        baseline_path.write_text(json.dumps(report.aggregate_metrics, indent=2), encoding="utf-8")
        print(f"[eval] Baseline saved to {baseline_path}")

    if args.fail_on_regression and report.regression_alerts:
        raise SystemExit(1)
    if not args.allow_partial and passed < report.num_samples:
        raise SystemExit(f"Eval failed: {passed}/{report.num_samples} samples passed")


if __name__ == "__main__":
    main()
