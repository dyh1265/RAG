"""Orchestrate YouTube lecture ingestion through the existing RAG pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.core.pipeline import IngestProgressFn, IngestResult, RAGPipeline
from backend.video.audio import prepare_whisper_audio
from backend.video.downloader import download_audio, download_video
from backend.video.frame_sampler import sample_frames
from backend.video.slide_chunker import tag_parsed_slide_chunks
from backend.video.slide_detector import detect_unique_slides
from backend.video.slide_pdf_builder import build_slides_pdf
from backend.video.transcriber import BaseTranscriber, build_transcriber
from backend.video.transcript_chunker import segments_to_chunks, youtube_doc_id
from backend.video.youtube_url import YouTubeURLError, validate_youtube_url


@dataclass
class YouTubeIngestResult:
    """Combined result from a YouTube ingest run."""

    ingest: IngestResult
    video_id: str | None = None
    title: str | None = None
    slides_pdf_path: str | None = None
    warnings: list[str] = field(default_factory=list)


def _merge_ingest_results(primary: IngestResult, secondary: IngestResult) -> IngestResult:
    """Combine transcript + slide indexing stats under one document."""
    chunks_by_type = dict(primary.chunks_by_type)
    for key, count in secondary.chunks_by_type.items():
        chunks_by_type[key] = chunks_by_type.get(key, 0) + count

    vectors_by_collection = dict(primary.vectors_by_collection)
    for key, count in secondary.vectors_by_collection.items():
        vectors_by_collection[key] = vectors_by_collection.get(key, 0) + count

    return IngestResult(
        doc_id=primary.doc_id,
        source_path=primary.source_path,
        chunk_count=primary.chunk_count + secondary.chunk_count,
        chunks_by_type=chunks_by_type,
        vectors_by_collection=vectors_by_collection,
        errors=[*primary.errors, *secondary.errors],
        skipped=primary.skipped and secondary.skipped,
    )


class YouTubeIngestor:
    def __init__(
        self,
        pipeline: RAGPipeline,
        settings: Settings,
        *,
        transcriber: BaseTranscriber | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._settings = settings
        self._transcriber = transcriber

    def ingest(
        self,
        url: str,
        *,
        tenant_id: str = "public",
        include_slides: bool = True,
        include_transcript: bool = True,
        sample_every_seconds: float | None = None,
        on_progress: IngestProgressFn | None = None,
    ) -> YouTubeIngestResult:
        if not include_transcript and not include_slides:
            raise ValueError("At least one of include_transcript or include_slides must be true")

        warnings: list[str] = []
        interval = (
            sample_every_seconds
            if sample_every_seconds is not None
            else self._settings.youtube_sample_every_seconds
        )

        def emit(stage: str, message: str, detail: dict[str, Any] | None = None) -> None:
            if on_progress is not None:
                on_progress(stage, message, detail)

        emit("validating", "Validating YouTube URL…")
        try:
            video_id = validate_youtube_url(url)
        except YouTubeURLError as exc:
            raise ValueError(str(exc)) from exc

        doc_id = youtube_doc_id(video_id)
        source_path = f"youtube:{video_id}"
        processed_dir = Path(self._settings.processed_docs_dir) / "youtube"

        result: IngestResult | None = None
        video_title: str | None = None
        slides_pdf_path: str | None = None
        work_dir: Path | None = None

        if include_transcript:
            emit("downloading_audio", "Downloading audio…", {"video_id": video_id})
            video_info, audio_path = download_audio(url, processed_dir=processed_dir)
            video_title = video_info.title
            work_dir = video_info.work_dir

            transcribe_path = video_info.work_dir / "audio_whisper.mp3"
            emit("transcribing", "Preparing audio for transcription…")
            prepare_whisper_audio(audio_path, transcribe_path)

            transcriber = self._transcriber or build_transcriber(self._settings)
            emit("transcribing", "Transcribing audio…")
            segments = transcriber.transcribe(transcribe_path)

            emit("chunking_transcript", f"Chunking {len(segments)} transcript segments…")
            chunks = segments_to_chunks(
                segments,
                video_id=video_id,
                video_title=video_info.title,
                doc_id=doc_id,
            )

            emit(
                "indexing_transcript",
                f"Indexing {len(chunks)} transcript chunks…",
                {"chunk_count": len(chunks)},
            )
            result = self._pipeline.index_chunks(
                chunks,
                doc_id=doc_id,
                source_path=source_path,
                tenant_id=tenant_id,
                on_progress=on_progress,
                clear_existing=True,
            )

        if include_slides:
            slide_result, slides_pdf_path, slide_title = self._ingest_slides(
                url,
                video_id=video_id,
                doc_id=doc_id,
                source_path=source_path,
                video_title=video_title,
                work_dir=work_dir,
                processed_dir=processed_dir,
                tenant_id=tenant_id,
                sample_every_seconds=interval,
                clear_existing=result is None,
                on_progress=on_progress,
            )
            video_title = video_title or slide_title
            if result is None:
                result = slide_result
            else:
                result = _merge_ingest_results(result, slide_result)

        assert result is not None
        return YouTubeIngestResult(
            ingest=result,
            video_id=video_id,
            title=video_title,
            slides_pdf_path=slides_pdf_path,
            warnings=warnings,
        )

    def _ingest_slides(
        self,
        url: str,
        *,
        video_id: str,
        doc_id: str,
        source_path: str,
        video_title: str | None,
        work_dir: Path | None,
        processed_dir: Path,
        tenant_id: str,
        sample_every_seconds: float,
        clear_existing: bool,
        on_progress: IngestProgressFn | None,
    ) -> tuple[IngestResult, str | None, str]:
        def emit(stage: str, message: str, detail: dict[str, Any] | None = None) -> None:
            if on_progress is not None:
                on_progress(stage, message, detail)

        emit("downloading_video", "Downloading video for slide extraction…")
        video_info, _video_path = download_video(url, processed_dir=processed_dir)
        resolved_work_dir = work_dir or video_info.work_dir
        title = video_title or video_info.title

        frames_dir = resolved_work_dir / "frames"
        emit(
            "sampling_frames",
            f"Sampling frames every {sample_every_seconds:.1f}s…",
            {"sample_every_seconds": sample_every_seconds},
        )
        sampled = sample_frames(
            _video_path,
            frames_dir,
            sample_every_seconds=sample_every_seconds,
        )

        slides_dir = resolved_work_dir / "slides"
        emit("detecting_slides", f"Detecting unique slides from {len(sampled)} frames…")
        slides = detect_unique_slides(sampled, slides_dir=slides_dir)

        if not slides:
            empty = IngestResult(
                doc_id=doc_id,
                source_path=source_path,
                chunk_count=0,
                errors=["No unique slides detected in video"],
            )
            return empty, None, title

        pdf_path = resolved_work_dir / "slides.pdf"
        emit("building_pdf", f"Building slides PDF ({len(slides)} pages)…")
        build_slides_pdf(slides, pdf_path)

        emit("indexing_slides", "Parsing and indexing slide PDF…")
        chunks, parse_errors = self._pipeline._ingestion.parse_safe(pdf_path)
        chunks = tag_parsed_slide_chunks(
            chunks,
            doc_id=doc_id,
            video_id=video_id,
            video_title=title,
            slides=slides,
        )

        slide_result = self._pipeline.index_chunks(
            chunks,
            doc_id=doc_id,
            source_path=source_path,
            tenant_id=tenant_id,
            on_progress=on_progress,
            clear_existing=clear_existing,
        )
        slide_result.errors.extend(str(exc) for exc in parse_errors)
        return slide_result, str(pdf_path), title
