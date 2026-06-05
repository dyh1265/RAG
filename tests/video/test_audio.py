"""Tests for Whisper-oriented audio helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from backend.video.audio import (
    WHISPER_MAX_BYTES,
    iter_whisper_chunks,
    whisper_chunk_duration_seconds,
)


def test_whisper_chunk_duration_infinite_when_under_limit():
    assert whisper_chunk_duration_seconds(WHISPER_MAX_BYTES - 1) == float("inf")


def test_whisper_chunk_duration_splits_oversized_file():
    # ~30 MiB MP3 estimate → multiple chunks
    size = int(WHISPER_MAX_BYTES * 1.2)
    duration = whisper_chunk_duration_seconds(size)
    assert duration < float("inf")
    assert duration >= 60.0


def test_iter_whisper_chunks_single_file_when_small(tmp_path: Path):
    audio = tmp_path / "short.mp3"
    audio.write_bytes(b"x" * 1024)
    chunks = iter_whisper_chunks(audio, tmp_path / "chunks")
    assert chunks == [(audio, 0.0)]


def test_iter_whisper_chunks_splits_when_over_limit(tmp_path: Path):
    audio = tmp_path / "long.mp3"
    audio.write_bytes(b"x" * (WHISPER_MAX_BYTES + 1))
    chunk_dir = tmp_path / "chunks"

    def _fake_probe(_path: Path) -> float:
        return 3600.0

    def _fake_ffmpeg(cmd: list[str]) -> None:
        out = Path(cmd[-1])
        out.write_bytes(b"chunk")

    with (
        patch("backend.video.audio._probe_duration_seconds", side_effect=_fake_probe),
        patch("backend.video.audio._run_ffmpeg", side_effect=_fake_ffmpeg),
    ):
        chunks = iter_whisper_chunks(audio, chunk_dir)

    assert len(chunks) >= 2
    assert chunks[0][1] == 0.0
    assert chunks[1][1] > 0.0
