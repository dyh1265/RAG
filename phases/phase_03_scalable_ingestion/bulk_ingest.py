"""
Bulk ingest CLI — queue PDFs to Celery or run synchronously.

Usage
-----
# Sync ingest (no Celery):
python phases/phase_03_scalable_ingestion/bulk_ingest.py data/raw/*.pdf --sync --hybrid --recursive-chunk

# Queue to Celery worker:
python phases/phase_03_scalable_ingestion/bulk_ingest.py data/raw/*.pdf --hybrid --recursive-chunk

Install: pip install -e ".[phase1,phase2,phase3]"
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from phases.phase_03_scalable_ingestion.embedding.redis_cache import EmbeddingCache
from phases.phase_03_scalable_ingestion.monitoring.metrics import start_metrics_server
from phases.phase_03_scalable_ingestion.pipeline.ingest_modes import IngestMode
from phases.phase_03_scalable_ingestion.pipeline.scalable_ingest import (
    ScalableIngestConfig,
    build_pipeline_from_flags,
    preload_pipeline,
    scalable_ingest,
)
from shared.config import get_settings


def ensure_services() -> None:
    """Fail fast with a clear message when Qdrant/Redis are unreachable."""
    settings = get_settings()
    cache = EmbeddingCache()
    if not cache.available():
        raise SystemExit(
            f"[bulk] Redis not reachable at {settings.redis_url}\n"
            "       Docker: cd docker && docker compose up -d qdrant redis"
        )
    try:
        from phases.phase_01_multimodal_ingestion.stores.qdrant_store import QdrantStore

        QdrantStore().client.get_collections()
    except Exception as exc:
        raise SystemExit(
            f"[bulk] Qdrant not reachable at {settings.qdrant_url}: {exc}\n"
            "       Docker: cd docker && docker compose up -d qdrant redis"
        ) from exc


from shared.pdf_paths import collect_pdf_paths


def collect_paths(
    patterns: list[str],
    glob_pattern: str | None,
    *,
    directory: str | None = None,
    recursive: bool = True,
) -> list[Path]:
    return collect_pdf_paths(
        directory=directory,
        recursive=recursive,
        patterns=patterns,
        glob_pattern=glob_pattern,
    )


def run_sync(paths: list[Path], args: argparse.Namespace) -> int:
    ensure_services()
    start_metrics_server()
    pipeline = build_pipeline_from_flags(
        hybrid=args.hybrid,
        recursive_chunk=args.recursive_chunk,
        semantic_chunk=args.semantic_chunk,
        use_colpali=args.colpali,
    )
    print("[bulk] Preloading models …")
    preload_ms = preload_pipeline(pipeline)
    print(f"[bulk] Models ready in {preload_ms:.0f}ms")

    mode = IngestMode.TEXT_ONLY if args.text_only else IngestMode.FULL
    cfg = ScalableIngestConfig(
        mode=mode,
        skip_unchanged=not args.force,
        use_cache=not args.no_cache,
        use_dedup=not args.no_dedup,
        force=args.force,
    )

    ok = skipped = failed = 0
    t0 = time.perf_counter()
    for i, path in enumerate(paths, start=1):
        print(f"[bulk] ({i}/{len(paths)}) {path.name} …", flush=True)
        try:
            result = scalable_ingest(pipeline, path, config=cfg)
            if result.skipped:
                skipped += 1
                print("       → skipped (unchanged)")
            elif result.errors and result.chunk_count == 0:
                failed += 1
                print(f"       → failed: {result.errors[0]}")
            else:
                ok += 1
                extra = f"cache hits {result.cache_hits}"
                if result.dedup_removed:
                    extra += f", dedup removed {result.dedup_removed}"
                print(f"       → {result.chunk_count} chunks ({extra})")
        except Exception as exc:
            failed += 1
            print(f"       → error: {exc}")

    elapsed = time.perf_counter() - t0
    print(
        f"\n[bulk] Done in {elapsed:.1f}s — "
        f"{ok} ingested, {skipped} skipped, {failed} failed"
    )
    return 1 if failed else 0


def run_async(paths: list[Path], args: argparse.Namespace) -> int:
    ensure_services()
    from phases.phase_03_scalable_ingestion.workers.tasks import ingest_document

    cache = EmbeddingCache()
    options = {
        "hybrid": args.hybrid,
        "recursive_chunk": args.recursive_chunk,
        "semantic_chunk": args.semantic_chunk,
        "use_colpali": args.colpali,
        "text_only": args.text_only,
        "skip_unchanged": not args.force,
        "use_cache": not args.no_cache,
        "use_dedup": not args.no_dedup,
        "force": args.force,
    }

    queued = 0
    skipped_done = 0
    for path in paths:
        if cache.available() and cache.is_ingest_done(str(path)) and not args.force:
            skipped_done += 1
            if skipped_done <= 3:
                print(f"[bulk] skip done: {path.name}")
            elif skipped_done == 4:
                print(f"[bulk] skip done: … ({len(paths) - 3} more in Redis ingest:done)")
            continue
        ingest_document.delay(str(path), options)
        queued += 1
        print(f"[bulk] queued: {path.name}")

    if skipped_done and not queued:
        print(
            f"\n[bulk] All {skipped_done} PDFs already ingested (Redis ingest:done). "
            "Use --sync to verify fingerprint skip, or --clear-done / --force to re-queue."
        )
    else:
        print(f"\n[bulk] Queued {queued} tasks ({skipped_done} already done) — monitor: docker compose logs -f ingest-worker")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk PDF ingestion")
    parser.add_argument("paths", nargs="*", help="PDF paths or globs")
    parser.add_argument("--dir", help="Ingest all PDFs in this directory")
    parser.add_argument("--no-recursive", action="store_true", help="With --dir, only top-level PDFs")
    parser.add_argument("--glob", dest="glob_pattern", help="Additional glob (e.g. data/raw/*.pdf)")
    parser.add_argument("--sync", action="store_true", help="Run inline without Celery")
    parser.add_argument("--text-only", action="store_true", help="Skip figure/page parsers")
    parser.add_argument("--hybrid", action="store_true")
    parser.add_argument("--recursive-chunk", action="store_true")
    parser.add_argument("--semantic-chunk", action="store_true")
    parser.add_argument("--colpali", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-ingest even when unchanged")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--no-dedup", action="store_true")
    parser.add_argument("--clear-done", action="store_true", help="Clear ingest:done Redis set")
    args = parser.parse_args()

    if args.clear_done:
        cache = EmbeddingCache()
        if cache.available():
            cache.clear_ingest_done()
            print("[bulk] Cleared ingest:done set")
        return

    paths = collect_paths(
        args.paths,
        args.glob_pattern,
        directory=args.dir,
        recursive=not args.no_recursive,
    )
    if not paths:
        raise SystemExit("No PDF paths matched")

    print(f"[bulk] Found {len(paths)} PDF(s)")
    code = run_sync(paths, args) if args.sync else run_async(paths, args)
    sys.exit(code)


if __name__ == "__main__":
    main()
