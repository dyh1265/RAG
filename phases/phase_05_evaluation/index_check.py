"""Check Qdrant for indexed documents; ingest when missing."""

from __future__ import annotations

from pathlib import Path

from phases.phase_01_multimodal_ingestion.parsers.base_parser import stable_doc_id
from phases.phase_01_multimodal_ingestion.stores.qdrant_store import COLLECTION_MAP
from shared.models import ChunkType, EvalSample
from shared.pipeline import RAGPipeline


def doc_is_indexed(pipeline: RAGPipeline, doc_id: str) -> bool:
    """True when at least one text chunk exists for doc_id."""
    chunks = pipeline.store.scroll_collection(
        COLLECTION_MAP[ChunkType.TEXT],
        filters={"doc_id": doc_id},
        limit=1,
    )
    return bool(chunks)


def required_doc_paths(samples: list[EvalSample]) -> list[Path]:
    paths = sorted({Path(s.doc_path) for s in samples if s.doc_path})
    return paths


def ensure_docs_indexed(
    pipeline: RAGPipeline,
    samples: list[EvalSample],
    *,
    ingest_if_missing: bool = False,
) -> list[str]:
    """
    Verify each sample's document is in Qdrant.

    Returns warning messages. Ingests when ingest_if_missing=True.
    """
    warnings: list[str] = []
    for path in required_doc_paths(samples):
        if not path.exists():
            warnings.append(f"Document not found on disk: {path}")
            continue

        doc_id = stable_doc_id(path)
        if doc_is_indexed(pipeline, doc_id):
            print(f"[eval] Indexed: {path.name} ({doc_id})")
            continue

        msg = f"Not indexed: {path.name} ({doc_id})"
        if ingest_if_missing:
            print(f"[eval] Ingesting {path} …")
            result = pipeline.ingest(path)
            print(
                f"[eval] Ingested {result.chunk_count} chunks "
                f"({', '.join(f'{n} {t}' for t, n in sorted(result.chunks_by_type.items()))})"
            )
        else:
            warnings.append(f"{msg} — re-run with --ingest-if-missing or ingest via demo.py")
    return warnings
