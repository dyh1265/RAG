"""Download YouTube audio (and optionally video) via yt-dlp."""

from __future__ import annotations

from pathlib import Path

from backend.video.models import YouTubeVideoInfo
from backend.video.youtube_url import canonical_watch_url, extract_video_id


class YouTubeDownloadError(RuntimeError):
    """Raised when yt-dlp fails to fetch media."""


def _work_dir(base: Path, video_id: str) -> Path:
    path = base / video_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_yt_dlp(url: str, outtmpl: str, fmt: str) -> dict:
    try:
        import yt_dlp
    except ImportError as exc:
        raise YouTubeDownloadError(
            "yt-dlp is not installed. Install with: pip install yt-dlp"
        ) from exc

    opts: dict = {
        "format": fmt,
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True)
    except Exception as exc:
        raise YouTubeDownloadError(
            f"Failed to download from YouTube ({url}): {exc}"
        ) from exc


def download_audio(
    url: str,
    *,
    processed_dir: Path,
) -> tuple[YouTubeVideoInfo, Path]:
    """Download audio-only media for transcription."""
    video_id = extract_video_id(url)
    work_dir = _work_dir(processed_dir, video_id)
    watch_url = canonical_watch_url(video_id)
    outtmpl = str(work_dir / "audio.%(ext)s")

    info = _run_yt_dlp(watch_url, outtmpl, "bestaudio/best")

    audio_path = _find_downloaded_file(work_dir, prefix="audio")
    if audio_path is None:
        raise YouTubeDownloadError(
            f"Audio download completed but no file found in {work_dir}"
        )

    video_info = YouTubeVideoInfo(
        video_id=video_id,
        title=str(info.get("title") or video_id),
        url=watch_url,
        duration_seconds=_float_or_none(info.get("duration")),
        work_dir=work_dir,
    )
    return video_info, audio_path


def download_video(
    url: str,
    *,
    processed_dir: Path,
) -> tuple[YouTubeVideoInfo, Path]:
    """Download best-effort MP4 for slide/frame extraction (PR 3)."""
    video_id = extract_video_id(url)
    work_dir = _work_dir(processed_dir, video_id)
    watch_url = canonical_watch_url(video_id)
    outtmpl = str(work_dir / "video.%(ext)s")
    fmt = 'bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best'

    info = _run_yt_dlp(watch_url, outtmpl, fmt)

    video_path = _find_downloaded_file(work_dir, prefix="video")
    if video_path is None:
        raise YouTubeDownloadError(
            f"Video download completed but no file found in {work_dir}"
        )

    video_info = YouTubeVideoInfo(
        video_id=video_id,
        title=str(info.get("title") or video_id),
        url=watch_url,
        duration_seconds=_float_or_none(info.get("duration")),
        work_dir=work_dir,
    )
    return video_info, video_path


def _find_downloaded_file(directory: Path, *, prefix: str) -> Path | None:
    for path in sorted(directory.glob(f"{prefix}.*")):
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
