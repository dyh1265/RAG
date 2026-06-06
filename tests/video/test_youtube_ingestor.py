"""Unit tests for YouTubeIngestor with mocked download/transcription."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.core.models import ChunkType, DocumentChunk, DocumentType
from backend.core.pipeline import IngestResult
from backend.video.frame_sampler import SampledFrame
from backend.video.models import SlideFrame, TranscriptSegment, YouTubeVideoInfo
from backend.video.transcriber import MockTranscriber
from backend.video.transcript_chunker import youtube_doc_id
from backend.video.youtube_ingestor import YouTubeIngestor

VIDEO_ID = "abc123xyz01"


def _video_info(work_dir: Path) -> YouTubeVideoInfo:
    return YouTubeVideoInfo(
        video_id=VIDEO_ID,
        title="Lecture",
        url=f"https://www.youtube.com/watch?v={VIDEO_ID}",
        duration_seconds=600.0,
        work_dir=work_dir,
    )


def test_ingestor_indexes_transcript_via_index_chunks(tmp_path):
    work_dir = tmp_path / "youtube" / VIDEO_ID
    work_dir.mkdir(parents=True)
    audio_file = work_dir / "audio.webm"
    audio_file.write_bytes(b"fake-audio")

    pipeline = MagicMock()
    pipeline.index_chunks.return_value = IngestResult(
        doc_id="doc1",
        source_path=f"youtube:{VIDEO_ID}",
        chunk_count=1,
        chunks_by_type={"transcript": 1},
        vectors_by_collection={"text_chunks": 1},
    )

    settings = MagicMock()
    settings.processed_docs_dir = str(tmp_path / "processed")

    transcriber = MockTranscriber(
        [TranscriptSegment(text="Hello world.", start=0.0, end=5.0)]
    )

    ingestor = YouTubeIngestor(pipeline, settings, transcriber=transcriber)

    def _fake_extract(_src: Path, dest: Path) -> Path:
        dest.write_bytes(b"fake-wav")
        return dest

    with (
        patch(
            "backend.video.youtube_ingestor.download_audio",
            return_value=(_video_info(work_dir), audio_file),
        ),
        patch(
            "backend.video.youtube_ingestor.prepare_whisper_audio",
            side_effect=_fake_extract,
        ),
    ):
        result = ingestor.ingest(
            f"https://www.youtube.com/watch?v={VIDEO_ID}",
            include_slides=False,
        )

    pipeline.index_chunks.assert_called_once()
    chunks = pipeline.index_chunks.call_args.args[0]
    assert len(chunks) >= 1
    assert chunks[0].metadata["video_id"] == VIDEO_ID
    assert result.video_id == VIDEO_ID
    assert result.ingest.chunk_count == 1


def test_ingestor_indexes_slides_via_parse_and_index_chunks(tmp_path):
    work_dir = tmp_path / "processed" / "youtube" / VIDEO_ID
    work_dir.mkdir(parents=True)
    video_file = work_dir / "video.mp4"
    video_file.write_bytes(b"fake-video")
    slides_pdf = work_dir / "slides.pdf"
    slides_pdf.write_bytes(b"%PDF-1.4 fake")

    pipeline = MagicMock()
    slide_chunk = DocumentChunk(
        id="p1",
        doc_id="wrong",
        source_path=str(slides_pdf),
        doc_type=DocumentType.PDF,
        chunk_type=ChunkType.PAGE_IMAGE,
        content="Slide text",
        page_number=1,
    )
    pipeline._ingestion.parse_safe.return_value = ([slide_chunk], [])
    pipeline.index_chunks.return_value = IngestResult(
        doc_id="doc1",
        source_path=f"youtube:{VIDEO_ID}",
        chunk_count=1,
        chunks_by_type={"page_image": 1},
        vectors_by_collection={"page_chunks": 1},
    )

    settings = MagicMock()
    settings.processed_docs_dir = str(tmp_path / "processed")
    settings.youtube_sample_every_seconds = 2.0
    settings.transcriber_provider = "mock"

    ingestor = YouTubeIngestor(pipeline, settings, transcriber=MockTranscriber([]))

    sampled = [SampledFrame(image_path=work_dir / "frame_00000.jpg", timestamp=0.0)]
    unique = [SlideFrame(image_path=work_dir / "slides" / "slide_001.png", timestamp=0.0, slide_number=1)]

    with (
        patch(
            "backend.video.youtube_ingestor.download_video",
            return_value=(
                _video_info(work_dir),
                video_file,
            ),
        ),
        patch("backend.video.youtube_ingestor.sample_frames", return_value=sampled),
        patch("backend.video.youtube_ingestor.detect_unique_slides", return_value=unique),
        patch("backend.video.youtube_ingestor.build_slides_pdf", return_value=slides_pdf),
    ):
        result = ingestor.ingest(
            f"https://www.youtube.com/watch?v={VIDEO_ID}",
            include_transcript=False,
            include_slides=True,
        )

    pipeline.index_chunks.assert_called_once()
    indexed_chunks = pipeline.index_chunks.call_args.args[0]
    assert indexed_chunks[0].doc_id == youtube_doc_id(VIDEO_ID)
    assert indexed_chunks[0].metadata["modality"] == "slide"
    assert indexed_chunks[0].metadata["video_id"] == VIDEO_ID
    assert result.slides_pdf_path == str(slides_pdf)
    assert result.ingest.chunk_count == 1
