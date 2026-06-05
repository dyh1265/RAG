"""Tests for OpenAI transcriber chunk merging."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.video.models import TranscriptSegment
from backend.video.transcriber import OpenAITranscriber, _segment_field


def test_segment_field_reads_sdk_object():
    class FakeSegment:
        text = "hello"
        start = 1.5
        end = 3.0

    assert _segment_field(FakeSegment(), "text") == "hello"
    assert _segment_field(FakeSegment(), "start") == 1.5


def test_segment_field_reads_dict():
    seg = {"text": "hi", "start": 0.0, "end": 1.0}
    assert _segment_field(seg, "text") == "hi"


def test_openai_transcriber_parses_sdk_segments(tmp_path: Path):
    audio = tmp_path / "lecture.mp3"
    audio.write_bytes(b"fake")

    class SdkSegment:
        def __init__(self, text: str, start: float, end: float) -> None:
            self.text = text
            self.start = start
            self.end = end

    class SdkResponse:
        segments = [SdkSegment("Hello world.", 0.0, 2.5)]
        text = "Hello world."

    transcriber = OpenAITranscriber(api_key="sk-test")
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = SdkResponse()

    segments = transcriber._transcribe_file(mock_client, audio)

    assert len(segments) == 1
    assert segments[0].text == "Hello world."
    assert segments[0].start == 0.0


def test_openai_transcriber_offsets_chunk_timestamps(tmp_path: Path):
    audio = tmp_path / "lecture.mp3"
    audio.write_bytes(b"fake")

    chunk_a = tmp_path / "whisper_chunks" / "whisper_chunk_000.mp3"
    chunk_b = tmp_path / "whisper_chunks" / "whisper_chunk_001.mp3"
    chunk_a.parent.mkdir(parents=True)
    chunk_a.write_bytes(b"a")
    chunk_b.write_bytes(b"b")

    def _fake_iter(_path: Path, _work: Path):
        return [(chunk_a, 0.0), (chunk_b, 600.0)]

    def _fake_transcribe(_client, path: Path):
        if path == chunk_a:
            return [TranscriptSegment(text="Part one.", start=0.0, end=10.0)]
        return [TranscriptSegment(text="Part two.", start=0.0, end=8.0)]

    transcriber = OpenAITranscriber(api_key="sk-test")

    with (
        patch("backend.video.transcriber.iter_whisper_chunks", side_effect=_fake_iter),
        patch.object(transcriber, "_transcribe_file", side_effect=_fake_transcribe),
        patch("openai.OpenAI", return_value=MagicMock()),
    ):
        segments = transcriber.transcribe(audio)

    assert len(segments) == 2
    assert segments[0].start == 0.0
    assert segments[1].start == 600.0
