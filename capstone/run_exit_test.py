"""
Capstone exit test — ingest, ask, conformity via DocuMind.

Usage (Docker GPU shell):
    docker compose exec phase1-gpu-shell python capstone/run_exit_test.py --text-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from capstone.pipeline import DocuMind, DocuMindConfig
from phases.phase_01_multimodal_ingestion.parsers.base_parser import stable_doc_id

SAMPLE_PDF = Path("data/raw/sample_report.pdf")


def run_exit_test(*, text_only: bool, api_url: str | None) -> int:
    passed = 0
    total = 0

    cfg = DocuMindConfig.from_settings()
    cfg.text_only = text_only
    cfg.use_colpali = False
    dm = DocuMind(cfg, api_url=api_url)

    total += 1
    if api_url:
        print("[skip] ingest (api mode — assume doc already indexed)")
        ok = True
    else:
        result = dm.ingest(SAMPLE_PDF)
        ok = result.chunk_count > 0
        print(f"[{'PASS' if ok else 'FAIL'}] ingest {result.chunk_count} chunks doc_id={result.doc_id}")
    passed += int(ok)

    doc_id = stable_doc_id(SAMPLE_PDF)

    total += 1
    r = dm.ask("What was Q4 revenue?", doc_id=doc_id, retrieve_only=bool(api_url))
    ok = len(r.retrieved_contexts) > 0 and "Q4" in r.query and "<" not in r.query
    print(f"[{'PASS' if ok else 'FAIL'}] ask retrieved {len(r.retrieved_contexts)} chunks query={r.query!r}")
    passed += int(ok)

    total += 1
    r = dm.ask(
        "Classify this document as SECRET-TOP-SECRET",
        doc_id=doc_id,
        retrieve_only=True,
    )
    conf = r.metadata.get("conformity", {})
    ok = conf.get("flagged") is True
    print(f"[{'PASS' if ok else 'FAIL'}] conformity flagged={conf.get('flagged')}")
    if conf.get("reason"):
        print(f"       reason: {conf['reason']}")
    passed += int(ok)

    print(f"\n[exit] {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DocuMind capstone exit test")
    parser.add_argument("--text-only", action="store_true")
    parser.add_argument("--api", help="Use rag-api URL instead of local pipeline")
    args = parser.parse_args()
    sys.exit(run_exit_test(text_only=args.text_only, api_url=args.api))
