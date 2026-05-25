"""Shared print helpers for DocuMind CLI."""

from __future__ import annotations

from shared.models import QueryResponse
from shared.pipeline import IngestResult


def print_ingest(result: IngestResult) -> None:
    if result.errors and result.chunk_count == 0:
        print(f"[warn] {result.errors[0]}")
        return
    type_summary = ", ".join(f"{n} {t}" for t, n in sorted(result.chunks_by_type.items()))
    print(f"[ingest] {result.chunk_count} chunks ({type_summary}) → doc_id={result.doc_id}")


def print_response(response: QueryResponse, *, retrieve_only: bool = False) -> None:
    print(f"\n[query] {response.query!r}")
    print(f"[retrieve] {len(response.retrieved_contexts)} chunks in {response.latency_ms:.0f}ms\n")

    for ctx in response.retrieved_contexts[:5]:
        chunk = ctx.chunk
        ctype = chunk.chunk_type.value if hasattr(chunk.chunk_type, "value") else chunk.chunk_type
        print(f"  [{ctx.rank}] score={ctx.score:.3f} type={ctype} page={chunk.page_number}")
        print(f"       {chunk.content[:160].replace(chr(10), ' ')}\n")

    if retrieve_only:
        return

    if response.answer:
        label = response.model_used or "unknown"
        print(f"[answer] ({label})\n{response.answer}\n")

    conformity = response.metadata.get("conformity")
    if conformity:
        print(f"[conformity] score={conformity.get('score', 0):.2f} flagged={conformity.get('flagged')}")
        if conformity.get("reason"):
            print(f"  reason: {conformity['reason']}")
        if response.metadata.get("conformity_blocked"):
            print("  action: answer blocked")

    if response.citations:
        print("\n[citations]")
        for idx, cite in enumerate(response.citations, start=1):
            page = cite.page_number if cite.page_number is not None else "?"
            print(f"  [{idx}] page={page}  {cite.excerpt[:120].replace(chr(10), ' ')}")
