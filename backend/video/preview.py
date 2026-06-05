"""Resolve previewable files for YouTube-ingested documents."""

from __future__ import annotations

from pathlib import Path

YOUTUBE_SOURCE_PREFIX = "youtube:"


def youtube_video_id_from_source(source_path: str) -> str | None:
    if source_path.startswith(YOUTUBE_SOURCE_PREFIX):
        video_id = source_path.removeprefix(YOUTUBE_SOURCE_PREFIX).strip()
        return video_id or None
    return None


def resolve_youtube_slides_pdf(source_path: str, processed_docs_dir: Path) -> Path | None:
    """Return slides.pdf for a YouTube document when slide extraction ran."""
    video_id = youtube_video_id_from_source(source_path)
    if not video_id:
        return None
    pdf_path = (processed_docs_dir / "youtube" / video_id / "slides.pdf").resolve()
    if pdf_path.is_file() and pdf_path.stat().st_size > 0:
        return pdf_path
    return None
