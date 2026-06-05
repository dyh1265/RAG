"""Citation metadata propagation for YouTube chunks."""

from __future__ import annotations

from backend.core.models import ChunkType, DocumentChunk, DocumentType, RetrievedContext
from backend.generation.answer_generator import _build_citations


def test_build_citations_includes_chunk_metadata():
    chunk = DocumentChunk(
        id="t1",
        doc_id="yt_doc",
        source_path="youtube:abc123xyz01",
        doc_type=DocumentType.VIDEO,
        chunk_type=ChunkType.TRANSCRIPT,
        content="The speaker explains treatment heterogeneity.",
        metadata={
            "source_kind": "youtube",
            "modality": "transcript",
            "video_id": "abc123xyz01",
            "start_time": 492.0,
            "end_time": 535.0,
            "youtube_url": "https://www.youtube.com/watch?v=abc123xyz01&t=492s",
        },
    )
    ctx = RetrievedContext(
        chunk=chunk,
        score=0.9,
        strategy="dense",
        rank=1,
    )
    citations = _build_citations([ctx])

    assert len(citations) == 1
    assert citations[0].metadata["modality"] == "transcript"
    assert citations[0].metadata["start_time"] == 492.0
