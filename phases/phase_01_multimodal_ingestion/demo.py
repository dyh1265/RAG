"""
Multimodal RAG demo CLI — thin wrapper around shared.pipeline.RAGPipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import os
import time

from phases.phase_01_multimodal_ingestion.parsers.base_parser import stable_doc_id
from shared.config import get_settings
from shared.models import QueryRequest
from shared.pipeline import PipelineConfig, RAGPipeline


def _print_ingest(result) -> None:
    if result.errors and result.chunk_count == 0:
        print(f"[warn] {result.errors[0]}")
        print("[error] No chunks extracted — check the PDF path.")
        return
    if result.errors:
        print(f"[warn] Parser encountered error(s): {result.errors[0]}")
    type_summary = ", ".join(f"{n} {t}" for t, n in sorted(result.chunks_by_type.items()))
    print(
        f"[ingest] Extracted {result.chunk_count} chunks from "
        f"{Path(result.source_path).name} ({type_summary})"
    )
    col_summary = ", ".join(
        f"{n} → {c}" for c, n in sorted(result.vectors_by_collection.items())
    )
    print(f"[ingest] Upserted {result.chunk_count} vectors into Qdrant ({col_summary})")


def _print_preload(ms: float) -> None:
    if ms > 500:
        print(f"[preload] embedding models ready in {ms:.0f}ms")
    else:
        print(f"[preload] models cached ({ms:.0f}ms)")


def _print_contexts(contexts) -> None:
    for ctx in contexts:
        chunk_type = ctx.chunk.chunk_type
        if hasattr(chunk_type, "value"):
            chunk_type = chunk_type.value
        print(
            f"  [{ctx.rank}] score={ctx.score:.3f}  type={chunk_type}  page={ctx.chunk.page_number}"
        )
        if ctx.chunk.section_path:
            print(f"       section={ctx.chunk.section_path}")
        if ctx.chunk.image_path:
            print(f"       image={ctx.chunk.image_path}")
        print(f"       {ctx.chunk.content[:200].replace(chr(10), ' ')}")
        print()


def _print_response(response, retrieve_only: bool, generate_ms: float | None = None) -> None:
    print(f"\n[query] '{response.query}'")
    print(f"[retrieve] {len(response.retrieved_contexts)} chunks in {response.latency_ms:.0f}ms\n")
    _print_contexts(response.retrieved_contexts)

    if retrieve_only:
        return

    if not response.answer:
        print("[answer] Skipped — no answer generated.")
        return

    label = response.model_used or "unknown"
    timing = f", {generate_ms:.0f}ms" if generate_ms is not None else ""
    print(f"[answer] ({label}{timing})\n")
    print(response.answer)
    print("\n[citations]")
    for idx, cite in enumerate(response.citations, start=1):
        page = cite.page_number if cite.page_number is not None else "?"
        print(f"  [{idx}] page={page}  chunk={cite.chunk_id[:8]}…")
        print(f"       {cite.excerpt[:160].replace(chr(10), ' ')}")
    conformity = response.metadata.get("conformity")
    if conformity:
        flagged = conformity.get("flagged")
        score = conformity.get("score")
        print(f"\n[conformity] score={score:.2f}  flagged={flagged}")
        if conformity.get("reason"):
            print(f"  reason: {conformity['reason']}")
        if response.metadata.get("conformity_blocked"):
            print("  action: answer blocked")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Multimodal RAG demo (Phases 1–2)")
    parser.add_argument("--doc", required=True, help="Path to a PDF document to ingest")
    parser.add_argument("--query", required=True, help="Question to answer")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--skip-ingest", action="store_true", help="Skip ingestion (doc already indexed)")
    parser.add_argument(
        "--skip-preload",
        action="store_true",
        help="Skip eager model load (retrieve timing will include cold-start)",
    )
    parser.add_argument(
        "--retrieve-only",
        action="store_true",
        help="Print retrieved chunks only (no LLM answer)",
    )
    parser.add_argument(
        "--colpali",
        action="store_true",
        help="Embed/search page_chunks with ColPali (ColQwen2) instead of bge-m3 text",
    )
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Text/table ingest and 1024-dim retrieval (overrides USE_COLPALI / --colpali)",
    )
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="Re-score candidates with bge-reranker-v2-m3 cross-encoder",
    )
    parser.add_argument(
        "--hybrid",
        action="store_true",
        help="BM25 + dense RRF for text_chunks (Phase 2; requires doc_id filter)",
    )
    parser.add_argument(
        "--recursive-chunk",
        action="store_true",
        help="Split large text blocks with RecursiveCharacterTextSplitter (Phase 2)",
    )
    parser.add_argument(
        "--semantic-chunk",
        action="store_true",
        help="Split large text blocks at semantic boundaries (Phase 2)",
    )
    parser.add_argument(
        "--flashrank",
        action="store_true",
        help="Re-score with FlashRank cross-encoder (Phase 2; lighter than --rerank)",
    )
    parser.add_argument(
        "--no-parent-expand",
        action="store_true",
        help="Disable child→parent chunk expansion after retrieval (Phase 2)",
    )
    parser.add_argument(
        "--no-section-paths",
        action="store_true",
        help="Disable heading-based section_path enrichment (Phase 2)",
    )
    parser.add_argument(
        "--no-context-enrich",
        action="store_true",
        help="Disable context_prefix before embedding (Phase 2)",
    )
    parser.add_argument(
        "--provider",
        choices=["ollama", "openai"],
        default="ollama",
        help="LLM provider for answer generation (default: ollama)",
    )
    parser.add_argument(
        "--no-taxonomy",
        action="store_true",
        help="Disable Phase 4 conformity validation",
    )
    parser.add_argument(
        "--block-forbidden",
        action="store_true",
        help="Block answers that violate classification taxonomy",
    )
    args = parser.parse_args()

    pdf_path = Path(args.doc)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Document not found: {pdf_path}")

    settings = get_settings()
    use_colpali = not args.text_only and (args.colpali or settings.use_colpali)
    use_hybrid = args.hybrid or settings.use_hybrid

    if not os.getenv("HF_TOKEN") and not os.getenv("HUGGING_FACE_HUB_TOKEN"):
        print(
            "[hint] Set HF_TOKEN in .env for faster Hugging Face downloads "
            "(optional — unauthenticated pulls still work)."
        )

    pipeline = RAGPipeline(
        PipelineConfig(
            use_rerank=args.rerank,
            use_flashrank=args.flashrank or settings.use_flashrank,
            use_colpali=use_colpali,
            use_hybrid=use_hybrid,
            use_recursive_chunker=args.recursive_chunk or settings.use_recursive_chunker,
            use_semantic_chunker=args.semantic_chunk or settings.use_semantic_chunker,
            use_section_paths=not args.no_section_paths and settings.use_section_paths,
            use_context_enrichment=not args.no_context_enrich and settings.use_context_enrichment,
            use_parent_expand=not args.no_parent_expand and settings.use_parent_expand,
            llm_provider=args.provider,
            use_taxonomy_validation=not args.no_taxonomy and settings.use_taxonomy_validation,
            block_forbidden_classifications=args.block_forbidden or settings.taxonomy_block_forbidden,
            text_only=args.text_only,
        )
    )

    if not args.skip_ingest:
        _print_ingest(pipeline.ingest(pdf_path))
    elif use_colpali:
        index_warning = pipeline.page_index_warning()
        if index_warning:
            print(f"[warn] {index_warning}")

    if not args.skip_preload:
        _print_preload(pipeline.preload_models())

    request = QueryRequest(
        query=args.query,
        top_k=args.top_k,
        filters={"doc_id": stable_doc_id(pdf_path)},
    )

    if args.retrieve_only:
        response = pipeline.query(request, generate_answer=False)
        _print_response(response, retrieve_only=True)
        return

    t0 = time.perf_counter()
    try:
        response = pipeline.query(request, provider=args.provider)
    except (ConnectionError, ValueError) as exc:
        response = pipeline.query(request, generate_answer=False)
        _print_response(response, retrieve_only=True)
        print(f"[answer] Skipped — {exc}")
        print("[answer] Re-run with --retrieve-only or fix the LLM provider.")
        return

    wall_ms = (time.perf_counter() - t0) * 1000
    generate_ms = wall_ms - (response.latency_ms or 0)
    _print_response(response, retrieve_only=False, generate_ms=max(generate_ms, 0))


if __name__ == "__main__":
    main()
