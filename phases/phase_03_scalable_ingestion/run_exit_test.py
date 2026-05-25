"""
Phase 3 exit test — bulk ingest 100+ PDFs, verify skip-on-unchanged and resume.

Usage
-----
python phases/phase_03_scalable_ingestion/run_exit_test.py --count 100 --text-only

Requires: Qdrant + Redis running, sample_report.pdf present.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

from phases.phase_01_multimodal_ingestion.stores.qdrant_store import COLLECTION_MAP
from phases.phase_03_scalable_ingestion.embedding.redis_cache import EmbeddingCache
from phases.phase_03_scalable_ingestion.pipeline.ingest_modes import IngestMode
from phases.phase_03_scalable_ingestion.pipeline.scalable_ingest import (
    ScalableIngestConfig,
    build_pipeline_from_flags,
    preload_pipeline,
    scalable_ingest,
)
from shared.models import ChunkType


def _sample_pdf() -> Path:
    path = Path("data/raw/sample_report.pdf")
    if not path.exists():
        raise FileNotFoundError(f"Missing {path} — run scripts/generate_sample_report.py")
    return path


def _doc_indexed(pipeline, doc_id: str) -> bool:
    chunks = pipeline.store.scroll_collection(
        COLLECTION_MAP[ChunkType.TEXT],
        filters={"doc_id": doc_id},
        limit=1,
    )
    return bool(chunks)


def run_exit_test(*, count: int, text_only: bool) -> int:
    source = _sample_pdf()
    cache = EmbeddingCache()
    if not cache.available():
        print("[exit] Redis not reachable — start redis (docker compose up -d redis)")
        return 1

    cache.clear_ingest_done()

    with tempfile.TemporaryDirectory(prefix="phase3_exit_") as tmp:
        tmp_dir = Path(tmp)
        paths: list[Path] = []
        for i in range(count):
            dest = tmp_dir / f"sample_{i:04d}.pdf"
            shutil.copy2(source, dest)
            paths.append(dest)

        pipeline = build_pipeline_from_flags()
        print("[exit] Preloading models …")
        preload_pipeline(pipeline)

        mode = IngestMode.TEXT_ONLY if text_only else IngestMode.FULL
        cfg = ScalableIngestConfig(mode=mode, skip_unchanged=True, use_cache=True)

        indexed = 0
        t0 = time.perf_counter()
        print(f"[exit] First pass — ingest {count} PDFs …")
        for i, path in enumerate(paths, start=1):
            result = scalable_ingest(pipeline, path, config=cfg)
            if result.skipped:
                print(f"  ({i}) unexpected skip: {path.name}")
                return 1
            if _doc_indexed(pipeline, result.doc_id):
                indexed += 1

        first_elapsed = time.perf_counter() - t0
        print(f"[exit] First pass: {indexed}/{count} indexed in {first_elapsed:.1f}s")

        skipped = 0
        t1 = time.perf_counter()
        print("[exit] Second pass — expect all skipped …")
        for path in paths:
            result = scalable_ingest(pipeline, path, config=cfg)
            if result.skipped:
                skipped += 1

        second_elapsed = time.perf_counter() - t1
        print(f"[exit] Second pass: {skipped}/{count} skipped in {second_elapsed:.1f}s")

        if indexed < count:
            print(f"[exit] FAIL — only {indexed}/{count} indexed")
            return 1
        if skipped < count:
            print(f"[exit] FAIL — only {skipped}/{count} skipped on re-run")
            return 1

        speedup = first_elapsed / second_elapsed if second_elapsed > 0 else float("inf")
        print(f"[exit] PASS — skip-re-embed speedup ~{speedup:.0f}x")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3 scalable ingestion exit test")
    parser.add_argument("--count", type=int, default=100, help="Number of PDF copies to ingest")
    parser.add_argument("--text-only", action="store_true", help="Faster text-only mode")
    args = parser.parse_args()
    sys.exit(run_exit_test(count=args.count, text_only=args.text_only))


if __name__ == "__main__":
    main()
