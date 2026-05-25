"""Admin endpoints — collection stats and document deletion."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from backend.api.dependencies import get_app_settings, get_pipeline
from backend.api.schemas import (
    CollectionStatsOut,
    DirectoryBrowseOut,
    DirectoryEntryOut,
    DocumentSuggestionsOut,
    DocumentSummaryOut,
)
from backend.ingestion.stores.qdrant_store import COLLECTION_MAP
from backend.core.config import Settings
from backend.core.data_browser import browse_directory
from backend.core.pdf_paths import resolve_under_base
from backend.core.pipeline import RAGPipeline
from backend.core.suggested_questions import build_suggested_questions

router = APIRouter()


def _display_name(source_path: str, doc_id: str) -> str:
    if source_path:
        return Path(source_path).name
    return doc_id[:12] + "…"


@router.get("/documents", response_model=list[DocumentSummaryOut])
async def list_documents(
    pipeline: RAGPipeline = Depends(get_pipeline),
    limit: int = 100,
) -> list[DocumentSummaryOut]:
    def _list() -> list[DocumentSummaryOut]:
        rows = pipeline.store.list_documents(limit=limit)
        return [
            DocumentSummaryOut(
                doc_id=row["doc_id"],
                name=_display_name(row.get("source_path", ""), row["doc_id"]),
                source_path=row.get("source_path") or "",
                chunk_count=row.get("chunk_count", 0),
            )
            for row in rows
        ]

    return await asyncio.to_thread(_list)


@router.get("/documents/{doc_id}/suggestions", response_model=DocumentSuggestionsOut)
async def document_suggestions(
    doc_id: str,
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> DocumentSuggestionsOut:
    if not doc_id.strip():
        raise HTTPException(status_code=400, detail="doc_id is required")

    source_path = await asyncio.to_thread(pipeline.store.get_document_source_path, doc_id)
    if not source_path:
        raise HTTPException(status_code=404, detail="Document not found")

    def _suggestions() -> DocumentSuggestionsOut:
        chunks = []
        for collection_name in ("text_chunks", "table_chunks", "figure_chunks"):
            chunks.extend(
                pipeline.store.scroll_collection(
                    collection_name,
                    filters={"doc_id": doc_id},
                    limit=40,
                )
            )

        name = _display_name(source_path, doc_id)
        questions = build_suggested_questions(doc_name=name, chunks=chunks)
        return DocumentSuggestionsOut(doc_id=doc_id, questions=questions)

    return await asyncio.to_thread(_suggestions)


def _resolve_pdf_path(source_path: str, settings: Settings) -> Path:
    """Resolve indexed PDF path and ensure it stays under data/."""
    data_base = Path(settings.data_dir).resolve()
    raw_base = Path(settings.raw_docs_dir).resolve()
    for base in (raw_base, data_base):
        try:
            resolved = resolve_under_base(source_path, base)
            if resolved.is_file() and resolved.suffix.lower() == ".pdf":
                return resolved
        except ValueError:
            continue
    candidate = Path(source_path).resolve()
    if candidate.is_file() and candidate.suffix.lower() == ".pdf":
        if data_base in candidate.parents or candidate == data_base:
            return candidate
    raise FileNotFoundError(source_path)


@router.get("/documents/{doc_id}/file")
async def get_document_file(
    doc_id: str,
    pipeline: RAGPipeline = Depends(get_pipeline),
    settings: Settings = Depends(get_app_settings),
) -> FileResponse:
    if not doc_id.strip():
        raise HTTPException(status_code=400, detail="doc_id is required")

    def _resolve() -> Path | None:
        source_path = pipeline.store.get_document_source_path(doc_id)
        if not source_path:
            return None
        try:
            return _resolve_pdf_path(source_path, settings)
        except FileNotFoundError:
            return None

    pdf_path = await asyncio.to_thread(_resolve)
    if pdf_path is None:
        raise HTTPException(status_code=404, detail="Document file not found")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
        headers={"Content-Disposition": f'inline; filename="{pdf_path.name}"'},
    )


@router.get("/directories", response_model=DirectoryBrowseOut)
async def browse_directories(
    path: str | None = Query(default=None, description="Directory under data/raw"),
    settings: Settings = Depends(get_app_settings),
) -> DirectoryBrowseOut:
    base = Path(settings.raw_docs_dir).resolve()

    def _browse() -> DirectoryBrowseOut:
        try:
            if path:
                resolve_under_base(path, base)
            listing = browse_directory(base, path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return DirectoryBrowseOut(
            path=listing.path,
            parent=listing.parent,
            entries=[
                DirectoryEntryOut(
                    name=e.name,
                    path=e.path,
                    kind=e.kind,
                    pdf=e.pdf,
                )
                for e in listing.entries
            ],
        )

    return await asyncio.to_thread(_browse)


@router.get("/collections", response_model=list[CollectionStatsOut])
async def list_collections(pipeline: RAGPipeline = Depends(get_pipeline)) -> list[CollectionStatsOut]:
    store = pipeline.store

    def _stats() -> list[CollectionStatsOut]:
        names = sorted(set(COLLECTION_MAP.values()))
        existing = {c.name for c in store.client.get_collections().collections}
        out: list[CollectionStatsOut] = []
        for name in names:
            if name not in existing:
                out.append(CollectionStatsOut(name=name))
                continue
            info = store.client.get_collection(name)
            out.append(
                CollectionStatsOut(
                    name=name,
                    points_count=info.points_count,
                    vector_size=store.collection_vector_size(name),
                )
            )
        return out

    return await asyncio.to_thread(_stats)


@router.delete("/doc/{doc_id}")
async def delete_document(doc_id: str, pipeline: RAGPipeline = Depends(get_pipeline)) -> dict:
    if not doc_id.strip():
        raise HTTPException(status_code=400, detail="doc_id is required")

    await asyncio.to_thread(pipeline.store.delete_doc, doc_id)
    return {"deleted": doc_id}
