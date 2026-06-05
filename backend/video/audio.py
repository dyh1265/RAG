"""Audio format conversion for transcription backends."""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

# OpenAI Whisper API hard limit (25 MiB).
WHISPER_MAX_BYTES = 25 * 1024 * 1024
# Target chunk size with headroom below the API cap.
WHISPER_TARGET_CHUNK_BYTES = 20 * 1024 * 1024
# Mono MP3 at 64 kbps ≈ 8 000 bytes/s — small enough for long lectures.
WHISPER_MP3_BITRATE = "64k"
WHISPER_MP3_BYTES_PER_SEC = 64_000 // 8


class AudioConversionError(RuntimeError):
    """Raised when ffmpeg cannot produce a transcription-ready audio file."""


def _run_ffmpeg(cmd: list[str]) -> None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise AudioConversionError(
            "ffmpeg is not installed or not on PATH. Install ffmpeg to transcribe audio."
        ) from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise AudioConversionError(stderr or "ffmpeg failed")


def _probe_duration_seconds(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise AudioConversionError(
            "ffprobe is not installed or not on PATH. Install ffmpeg to transcribe audio."
        ) from exc

    if result.returncode != 0:
        raise AudioConversionError(
            f"ffprobe failed for {path}: {(result.stderr or '').strip()}"
        )

    try:
        return float((result.stdout or "").strip())
    except ValueError as exc:
        raise AudioConversionError(f"Could not read audio duration for {path}") from exc


def extract_audio(video_or_audio_path: Path, out_path: Path) -> Path:
    """Convert arbitrary media to mono 16 kHz WAV (legacy / debugging)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_or_audio_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(out_path),
        ]
    )

    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise AudioConversionError(f"ffmpeg produced an empty file: {out_path}")

    return out_path


def prepare_whisper_audio(video_or_audio_path: Path, out_path: Path) -> Path:
    """Convert media to compact mono MP3 suitable for the Whisper API (≤25 MiB)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_or_audio_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            WHISPER_MP3_BITRATE,
            str(out_path),
        ]
    )

    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise AudioConversionError(f"ffmpeg produced an empty file: {out_path}")

    return out_path


def whisper_chunk_duration_seconds(file_size: int, *, max_bytes: int = WHISPER_MAX_BYTES) -> float:
    """Seconds per chunk so encoded MP3 parts stay under ``max_bytes``."""
    if file_size <= max_bytes:
        return math.inf
    chunks_needed = math.ceil(file_size / WHISPER_TARGET_CHUNK_BYTES)
    total_duration = file_size / WHISPER_MP3_BYTES_PER_SEC
    return max(60.0, total_duration / chunks_needed)


def iter_whisper_chunks(
    audio_path: Path,
    work_dir: Path,
    *,
    max_bytes: int = WHISPER_MAX_BYTES,
) -> list[tuple[Path, float]]:
    """Return one or more MP3 paths with start offsets for Whisper upload."""
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    size = audio_path.stat().st_size
    if size <= max_bytes:
        return [(audio_path, 0.0)]

    work_dir.mkdir(parents=True, exist_ok=True)
    duration = _probe_duration_seconds(audio_path)
    chunk_seconds = whisper_chunk_duration_seconds(size, max_bytes=max_bytes)
    if not math.isfinite(chunk_seconds):
        return [(audio_path, 0.0)]

    chunks: list[tuple[Path, float]] = []
    start = 0.0
    index = 0
    while start < duration - 0.01:
        remaining = duration - start
        segment_len = min(chunk_seconds, remaining)
        out_path = work_dir / f"whisper_chunk_{index:03d}.mp3"
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{start:.3f}",
                "-i",
                str(audio_path),
                "-t",
                f"{segment_len:.3f}",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-b:a",
                WHISPER_MP3_BITRATE,
                str(out_path),
            ]
        )
        if not out_path.is_file() or out_path.stat().st_size == 0:
            raise AudioConversionError(f"ffmpeg produced an empty chunk: {out_path}")
        chunks.append((out_path, start))
        start += segment_len
        index += 1

    return chunks or [(audio_path, 0.0)]
