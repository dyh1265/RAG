"""Convert timestamped transcript segments into DocumentChunks."""

from __future__ import annotations

import hashlib

from backend.core.models import ChunkType, DocumentChunk, DocumentType
from backend.video.models import TranscriptSegment
from backend.video.youtube_url import timestamp_url


def youtube_doc_id(video_id: str) -> str:
    return hashlib.sha256(f"youtube:{video_id}".encode()).hexdigest()[:16]


def _chunk_id(doc_id: str, start: float, end: float) -> str:
    key = f"{doc_id}|transcript|{start:.2f}|{end:.2f}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def segments_to_chunks(
    segments: list[TranscriptSegment],
    *,
    video_id: str,
    video_title: str,
    doc_id: str | None = None,
    target_window_seconds: float = 75.0,
    max_tokens: int = 700,
    overlap_seconds: float = 5.0,
) -> list[DocumentChunk]:
    """Group Whisper segments into retrieval-sized transcript chunks."""
    if not segments:
        return []

    resolved_doc_id = doc_id or youtube_doc_id(video_id)
    source_path = f"youtube:{video_id}"
    chunks: list[DocumentChunk] = []

    window: list[TranscriptSegment] = []

    def window_text(segs: list[TranscriptSegment]) -> str:
        return " ".join(s.text.strip() for s in segs if s.text.strip())

    def emit(segs: list[TranscriptSegment]) -> list[TranscriptSegment]:
        text = window_text(segs)
        if not text:
            return []
        start = segs[0].start
        end = segs[-1].end
        chunks.append(
            DocumentChunk(
                id=_chunk_id(resolved_doc_id, start, end),
                doc_id=resolved_doc_id,
                source_path=source_path,
                doc_type=DocumentType.VIDEO,
                chunk_type=ChunkType.TRANSCRIPT,
                content=text,
                metadata={
                    "source_kind": "youtube",
                    "modality": "transcript",
                    "video_id": video_id,
                    "video_title": video_title,
                    "start_time": start,
                    "end_time": end,
                    "youtube_url": timestamp_url(video_id, start),
                },
            )
        )
        if overlap_seconds <= 0:
            return []
        cutoff = end - overlap_seconds
        return [s for s in segs if s.end > cutoff]

    for segment in segments:
        if not segment.text.strip():
            continue

        if not window:
            window = [segment]
            continue

        candidate = window + [segment]
        duration = segment.end - window[0].start
        tokens = _estimate_tokens(window_text(candidate))

        if duration >= target_window_seconds or tokens >= max_tokens:
            window = emit(window)
            if window:
                window = window + [segment]
            else:
                window = [segment]
        else:
            window.append(segment)

    if window:
        emit(window)

    return chunks
