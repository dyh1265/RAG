"""Pluggable speech-to-text backends for YouTube audio."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from backend.core.config import Settings
from backend.video.audio import iter_whisper_chunks
from backend.video.models import TranscriptSegment


def _segment_field(segment: object, name: str, default=None):
    """Read a field from an OpenAI SDK object or a plain dict."""
    if isinstance(segment, dict):
        return segment.get(name, default)
    return getattr(segment, name, default)


class BaseTranscriber(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path) -> list[TranscriptSegment]:
        ...


class MockTranscriber(BaseTranscriber):
    """Deterministic transcriber for unit tests."""

    def __init__(self, segments: list[TranscriptSegment] | None = None) -> None:
        self._segments = segments or [
            TranscriptSegment(
                text="The speaker explains treatment heterogeneity.",
                start=0.0,
                end=12.0,
            ),
            TranscriptSegment(
                text="Variation in treatment response differs across individuals.",
                start=12.0,
                end=28.0,
            ),
        ]

    def transcribe(self, audio_path: Path) -> list[TranscriptSegment]:
        if not audio_path.is_file():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        return list(self._segments)


class OpenAITranscriber(BaseTranscriber):
    """Transcribe via OpenAI Whisper API (verbose_json for timestamps)."""

    def __init__(self, *, api_key: str, model: str = "whisper-1") -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI transcription")
        self._api_key = api_key
        self._model = model

    def _transcribe_file(self, client, audio_path: Path) -> list[TranscriptSegment]:
        with audio_path.open("rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=self._model,
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

        raw_segments = getattr(response, "segments", None) or []
        segments: list[TranscriptSegment] = []
        for seg in raw_segments:
            text = str(_segment_field(seg, "text", "") or "").strip()
            if not text:
                continue
            start = float(_segment_field(seg, "start", 0.0) or 0.0)
            end = float(_segment_field(seg, "end", start) or start)
            segments.append(TranscriptSegment(text=text, start=start, end=end))

        if not segments:
            full_text = (getattr(response, "text", None) or "").strip()
            if full_text:
                segments.append(TranscriptSegment(text=full_text, start=0.0, end=0.0))

        return segments

    def transcribe(self, audio_path: Path) -> list[TranscriptSegment]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "openai package is not installed. Install with: pip install openai"
            ) from exc

        client = OpenAI(api_key=self._api_key)
        chunks = iter_whisper_chunks(audio_path, audio_path.parent / "whisper_chunks")
        merged: list[TranscriptSegment] = []

        for chunk_path, offset in chunks:
            for segment in self._transcribe_file(client, chunk_path):
                merged.append(
                    TranscriptSegment(
                        text=segment.text,
                        start=segment.start + offset,
                        end=segment.end + offset,
                    )
                )

        return merged


def build_transcriber(settings: Settings) -> BaseTranscriber:
    provider = (settings.transcriber_provider or "openai").lower()
    if provider == "mock":
        return MockTranscriber()
    if provider == "openai":
        return OpenAITranscriber(api_key=settings.openai_api_key)
    raise ValueError(f"Unknown transcriber provider: {settings.transcriber_provider}")
