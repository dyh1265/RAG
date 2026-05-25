"""
DocuMind CLI — capstone entry point.

Usage
-----
python -m capstone.cli ingest --doc data/raw/sample_report.pdf
python -m capstone.cli ask --doc data/raw/sample_report.pdf --query "What was Q4 revenue?"
python -m capstone.cli ask --api http://localhost:8002 --doc-id ed7d53f9b08caa39 --query "..."
python -m capstone.cli eval --tag sample-report --retrieve-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from capstone.display import print_ingest, print_response
from capstone.pipeline import DocuMind, DocuMindConfig


def _build_config(args: argparse.Namespace) -> DocuMindConfig:
    cfg = DocuMindConfig.from_settings()
    if args.text_only:
        cfg.text_only = True
        cfg.use_colpali = False
    if args.no_hybrid:
        cfg.use_hybrid = False
    if args.no_taxonomy:
        cfg.use_taxonomy_validation = False
    if args.block_forbidden:
        cfg.block_forbidden_classifications = True
    if getattr(args, "provider", None):
        cfg.llm_provider = args.provider
    return cfg


def cmd_ingest(args: argparse.Namespace) -> int:
    dm = DocuMind(_build_config(args), api_url=args.api)
    result = dm.ingest(args.doc)
    print_ingest(result)
    return 0 if result.chunk_count > 0 or result.skipped else 1


def cmd_ingest_dir(args: argparse.Namespace) -> int:
    from pathlib import Path

    from shared.config import get_settings
    from shared.directory_ingest import ingest_directory
    from shared.pdf_paths import resolve_under_base

    cfg = _build_config(args)
    recursive = not args.no_recursive

    if args.api:
        from capstone.client import DocuMindApiClient

        client = DocuMindApiClient(args.api)
        summary = client.ingest_directory(args.dir, recursive=recursive)
        print(
            f"[ingest-dir] {summary['directory']}: "
            f"{summary['ingested']} ingested, {summary['skipped']} skipped, "
            f"{summary['failed']} failed ({summary['total_files']} PDFs)"
        )
        return 0 if summary["failed"] == 0 else 1

    dm = DocuMind(cfg)
    if not args.skip_preload:
        ms = dm.preload_models()
        if ms > 500:
            print(f"[preload] models ready in {ms:.0f}ms")

    base = Path(get_settings().raw_docs_dir).resolve()
    try:
        directory = resolve_under_base(args.dir, base)
    except ValueError as exc:
        print(f"[error] {exc}")
        return 1

    def _progress(i: int, total: int, path: Path) -> None:
        print(f"[ingest-dir] ({i}/{total}) {path.name} …", flush=True)

    summary = ingest_directory(
        dm.pipeline,
        directory,
        recursive=recursive,
        on_progress=_progress,
    )
    print(
        f"\n[ingest-dir] Done — {summary.ingested} ingested, "
        f"{summary.skipped} skipped, {summary.failed} failed "
        f"({summary.total_files} PDFs in {summary.directory})"
    )
    for result in summary.results:
        if result.errors and result.chunk_count == 0:
            print(f"  FAIL {Path(result.source_path).name}: {result.errors[0]}")
        elif result.skipped:
            print(f"  skip {Path(result.source_path).name}")
        elif result.chunk_count:
            print(f"  ok   {Path(result.source_path).name} ({result.chunk_count} chunks, {result.doc_id})")
    return 0 if summary.ok else 1


def cmd_ask(args: argparse.Namespace) -> int:
    dm = DocuMind(_build_config(args), api_url=args.api)
    if not args.api and not args.skip_preload:
        ms = dm.preload_models()
        if ms > 500:
            print(f"[preload] models ready in {ms:.0f}ms")

    response = dm.ask(
        args.query,
        doc=args.doc,
        doc_id=args.doc_id,
        top_k=args.top_k,
        provider=args.provider,
        retrieve_only=args.retrieve_only,
        block_forbidden=args.block_forbidden or None,
    )
    print_response(response, retrieve_only=args.retrieve_only)
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from phases.phase_05_evaluation.run_full_eval import load_golden_set, run_eval, save_report
    from shared.models import ChunkType

    golden_path = Path(args.golden or "data/benchmarks/golden_qa.json")
    samples = load_golden_set(golden_path)
    if args.tag:
        samples = [s for s in samples if args.tag in s.tags]
    if args.text_only:
        skipped = [
            s.id
            for s in samples
            if s.chunk_type_focus in (ChunkType.FIGURE, ChunkType.PAGE_IMAGE)
        ]
        if skipped:
            print(f"[eval] skipping {len(skipped)} multimodal sample(s) in text-only mode: {', '.join(skipped)}")
        samples = [
            s
            for s in samples
            if s.chunk_type_focus not in (ChunkType.FIGURE, ChunkType.PAGE_IMAGE)
        ]

    cfg = _build_config(args)
    dm = DocuMind(cfg, api_url=args.api)
    if args.api:
        print("[error] eval requires local pipeline (omit --api)")
        return 1

    if args.ingest_if_missing:
        from phases.phase_05_evaluation.index_check import ensure_docs_indexed

        for msg in ensure_docs_indexed(dm.pipeline, samples, ingest_if_missing=True):
            print(msg)

    report = run_eval(
        samples,
        system_label="documind",
        pipeline=dm.pipeline,
        generate_answer=not args.retrieve_only,
        provider=args.provider,
    )
    json_path, html_path = save_report(report)
    passed = sum(1 for r in report.sample_results if r.passed)
    total = len(report.sample_results)
    print(f"\n[eval] {passed}/{total} passed")
    print(f"[eval] report → {html_path}")
    return 0 if passed == total else 1


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--api", help="Use Phase 6 rag-api base URL (e.g. http://localhost:8002)")
    parser.add_argument("--text-only", action="store_true", help="Text/table ingest and retrieval")
    parser.add_argument("--no-hybrid", action="store_true")
    parser.add_argument("--no-taxonomy", action="store_true")
    parser.add_argument("--block-forbidden", action="store_true")


def main() -> None:
    parser = argparse.ArgumentParser(prog="documind", description="DocuMind capstone CLI")
    common = argparse.ArgumentParser(add_help=False)
    _add_common_args(common)
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", parents=[common], help="Ingest a PDF")
    p_ingest.add_argument("--doc", required=True, help="Path to PDF")
    p_ingest.set_defaults(func=cmd_ingest)

    p_ingest_dir = sub.add_parser("ingest-dir", parents=[common], help="Ingest all PDFs in a directory")
    p_ingest_dir.add_argument("--dir", required=True, help="Directory under data/raw")
    p_ingest_dir.add_argument("--no-recursive", action="store_true", help="Only PDFs in the top level")
    p_ingest_dir.add_argument("--skip-preload", action="store_true")
    p_ingest_dir.set_defaults(func=cmd_ingest_dir)

    p_ask = sub.add_parser("ask", parents=[common], help="Ask a question")
    p_ask.add_argument("--query", required=True)
    p_ask.add_argument("--doc", help="PDF path (derives doc_id)")
    p_ask.add_argument("--doc-id", help="Indexed doc_id (required with --api if no --doc)")
    p_ask.add_argument("--top-k", type=int, default=5)
    p_ask.add_argument("--provider", choices=["openai", "ollama"], default="openai")
    p_ask.add_argument("--retrieve-only", action="store_true")
    p_ask.add_argument("--skip-preload", action="store_true")
    p_ask.set_defaults(func=cmd_ask)

    p_eval = sub.add_parser("eval", parents=[common], help="Run golden-set evaluation")
    p_eval.add_argument("--golden", help="Path to golden_qa.json")
    p_eval.add_argument("--tag", help="Filter samples by tag")
    p_eval.add_argument("--retrieve-only", action="store_true")
    p_eval.add_argument("--ingest-if-missing", action="store_true")
    p_eval.add_argument("--provider", choices=["openai", "ollama"], default="openai")
    p_eval.set_defaults(func=cmd_eval)

    args = parser.parse_args()
    if args.command == "ask" and not args.doc and not args.doc_id:
        parser.error("ask requires --doc or --doc-id")

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
