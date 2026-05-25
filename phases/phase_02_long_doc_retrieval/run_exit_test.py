"""Phase 2 long-document exit test runner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from phases.phase_01_multimodal_ingestion.parsers.base_parser import stable_doc_id
from phases.phase_02_long_doc_retrieval.benchmark import DEFAULT_BENCHMARK_PATH, evaluate_samples, load_benchmark
from shared.config import get_settings
from shared.models import QueryRequest
from shared.pipeline import PipelineConfig, RAGPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2 long-document retrieval exit test")
    parser.add_argument(
        "--benchmark",
        default=str(DEFAULT_BENCHMARK_PATH),
        help="Path to long_doc_qa.json",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--hybrid", action="store_true", help="Enable BM25 + dense hybrid")
    parser.add_argument("--recursive-chunk", action="store_true")
    parser.add_argument("--semantic-chunk", action="store_true")
    parser.add_argument("--flashrank", action="store_true")
    parser.add_argument("--min-recall", type=float, default=0.75, help="Minimum mean page recall")
    args = parser.parse_args()

    benchmark = load_benchmark(args.benchmark)
    doc_path = Path(benchmark.doc_path)
    if not doc_path.exists():
        raise FileNotFoundError(f"Benchmark document not found: {doc_path}")

    doc_id = stable_doc_id(doc_path)

    settings = get_settings()
    pipeline = RAGPipeline(
        PipelineConfig(
            use_hybrid=args.hybrid or settings.use_hybrid,
            use_recursive_chunker=args.recursive_chunk or settings.use_recursive_chunker,
            use_semantic_chunker=args.semantic_chunk or settings.use_semantic_chunker,
            use_flashrank=args.flashrank or settings.use_flashrank,
        )
    )

    if not args.skip_ingest:
        result = pipeline.ingest(doc_path)
        print(
            f"[ingest] {result.chunk_count} chunks "
            f"({', '.join(f'{n} {t}' for t, n in sorted(result.chunks_by_type.items()))})"
        )
    else:
        pipeline.preload_models()

    results: dict[str, list] = {}
    for sample in benchmark.samples:
        request = QueryRequest(
            query=sample.question,
            top_k=args.top_k,
            filters={"doc_id": doc_id},
        )
        contexts = pipeline.retrieve(request)
        results[sample.question] = contexts
        pages = sorted({c.chunk.page_number for c in contexts if c.chunk.page_number})
        print(f"\n[{sample.id}] {sample.question}")
        print(f"  expected pages ~{sample.expected_pages}  retrieved pages={pages}")

    mean_recall, per_sample = evaluate_samples(results, benchmark)
    passed_count = sum(1 for _, passed in per_sample if passed)
    print(f"\n[exit-test] page recall@{args.top_k}: {mean_recall:.0%} ({passed_count}/{len(per_sample)})")

    for sample, passed in per_sample:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {sample.id}")

    if mean_recall < args.min_recall:
        raise SystemExit(
            f"Exit test failed: recall {mean_recall:.0%} < threshold {args.min_recall:.0%}"
        )


if __name__ == "__main__":
    main()
