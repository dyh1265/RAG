"""Re-tag PDF-parsed slide chunks with YouTube metadata and a shared doc_id."""

from __future__ import annotations

from backend.core.models import DocumentChunk, DocumentType
from backend.video.models import SlideFrame
from backend.video.youtube_url import timestamp_url


def tag_parsed_slide_chunks(
    chunks: list[DocumentChunk],
    *,
    doc_id: str,
    video_id: str,
    video_title: str,
    slides: list[SlideFrame],
) -> list[DocumentChunk]:
    """Stamp parsed PDF chunks so they belong to the parent YouTube document."""
    by_page = {slide.slide_number: slide for slide in slides}
    source_path = f"youtube:{video_id}"
    tagged: list[DocumentChunk] = []

    for chunk in chunks:
        slide = by_page.get(chunk.page_number) if chunk.page_number is not None else None
        metadata = dict(chunk.metadata)
        metadata.update(
            {
                "source_kind": "youtube",
                "modality": "slide",
                "video_id": video_id,
                "video_title": video_title,
                "slide_number": slide.slide_number if slide else chunk.page_number,
                "timestamp": slide.timestamp if slide else None,
            }
        )
        if slide is not None:
            metadata["youtube_url"] = timestamp_url(video_id, slide.timestamp)

        tagged.append(
            chunk.model_copy(
                update={
                    "doc_id": doc_id,
                    "source_path": source_path,
                    "doc_type": DocumentType.VIDEO,
                    "metadata": metadata,
                }
            )
        )

    return tagged
