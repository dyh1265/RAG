"""Tests for transcript segment → DocumentChunk conversion."""

from __future__ import annotations

from backend.core.models import ChunkType, DocumentType
from backend.video.models import TranscriptSegment
from backend.video.transcript_chunker import segments_to_chunks, youtube_doc_id


VIDEO_ID = "abc123xyz01"


def test_segments_are_grouped_into_chunks():
    segments = [
        TranscriptSegment(text=f"Sentence {i}.", start=i * 10.0, end=(i + 1) * 10.0)
        for i in range(12)
    ]
    chunks = segments_to_chunks(
        segments,
        video_id=VIDEO_ID,
        video_title="Lecture on heterogeneity",
        target_window_seconds=30.0,
        max_tokens=50,
    )
    assert len(chunks) >= 2
    assert all(c.chunk_type == ChunkType.TRANSCRIPT for c in chunks)


def test_metadata_contains_timestamps_and_video_id():
    segments = [
        TranscriptSegment(text="Opening remarks.", start=0.0, end=8.0),
        TranscriptSegment(text="Main topic begins.", start=8.0, end=20.0),
    ]
    chunks = segments_to_chunks(
        segments,
        video_id=VIDEO_ID,
        video_title="Test Lecture",
    )
    assert len(chunks) == 1
    meta = chunks[0].metadata
    assert meta["video_id"] == VIDEO_ID
    assert meta["start_time"] == 0.0
    assert meta["end_time"] == 20.0
    assert meta["modality"] == "transcript"
    assert VIDEO_ID in meta["youtube_url"]


def test_doc_id_is_stable():
    doc_id = youtube_doc_id(VIDEO_ID)
    chunks = segments_to_chunks(
        [TranscriptSegment(text="Hello.", start=0.0, end=1.0)],
        video_id=VIDEO_ID,
        video_title="T",
        doc_id=doc_id,
    )
    assert chunks[0].doc_id == doc_id
    assert youtube_doc_id(VIDEO_ID) == doc_id


def test_empty_transcript_returns_no_chunks():
    assert segments_to_chunks([], video_id=VIDEO_ID, video_title="T") == []


def test_video_doc_type():
    chunks = segments_to_chunks(
        [TranscriptSegment(text="Hi.", start=0.0, end=1.0)],
        video_id=VIDEO_ID,
        video_title="T",
    )
    assert chunks[0].doc_type == DocumentType.VIDEO
