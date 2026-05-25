"""Ingest every PDF in a directory via RAGPipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from shared.pdf_paths import collect_pdf_paths
from shared.pipeline import IngestResult, RAGPipeline


@dataclass
class DirectoryIngestSummary:
    directory: str
    total_files: int
    ingested: int
    skipped: int
    failed: int
    results: list[IngestResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.failed == 0


def ingest_directory(
    pipeline: RAGPipeline,
    directory: str | Path,
    *,
    recursive: bool = True,
    on_progress: Callable[[int, int, Path], None] | None = None,
) -> DirectoryIngestSummary:
    """Parse, chunk, embed, and index all PDFs under directory."""
    root = Path(directory)
    paths = collect_pdf_paths(directory=root, recursive=recursive)
    ingested = skipped = failed = 0
    results: list[IngestResult] = []

    for i, path in enumerate(paths, start=1):
        if on_progress:
            on_progress(i, len(paths), path)
        try:
            result = pipeline.ingest(path)
            results.append(result)
            if result.skipped:
                skipped += 1
            elif result.errors and result.chunk_count == 0:
                failed += 1
            else:
                ingested += 1
        except Exception as exc:
            failed += 1
            results.append(
                IngestResult(
                    doc_id="",
                    source_path=str(path),
                    chunk_count=0,
                    errors=[str(exc)],
                )
            )

    return DirectoryIngestSummary(
        directory=str(root.resolve()),
        total_files=len(paths),
        ingested=ingested,
        skipped=skipped,
        failed=failed,
        results=results,
    )
