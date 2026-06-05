"""YouTube URL validation and video-id extraction."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_YOUTUBE_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtu.be",
    }
)

_VIDEO_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


class YouTubeURLError(ValueError):
    """Raised when a URL is not a supported YouTube link."""


def _normalize_host(netloc: str) -> str:
    return netloc.lower().removeprefix("www.")


def extract_video_id(url: str) -> str:
    """Extract an 11-character YouTube video id from a watch, short, or youtu.be URL."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise YouTubeURLError(f"Unsupported URL scheme: {parsed.scheme or '(none)'}")

    host = _normalize_host(parsed.netloc)
    if host not in {h.removeprefix("www.") for h in _YOUTUBE_HOSTS}:
        raise YouTubeURLError(f"Not a YouTube URL: {url}")

    if host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
    else:
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts and path_parts[0] in {"shorts", "embed", "live", "v"}:
            video_id = path_parts[1] if len(path_parts) > 1 else ""
        else:
            video_id = parse_qs(parsed.query).get("v", [""])[0]

    if not _VIDEO_ID_RE.match(video_id):
        raise YouTubeURLError(f"Could not extract a valid video id from: {url}")

    return video_id


def canonical_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def timestamp_url(video_id: str, seconds: float | int) -> str:
    return f"{canonical_watch_url(video_id)}&t={int(seconds)}s"


def validate_youtube_url(url: str) -> str:
    """Validate a YouTube URL and return the extracted video id."""
    return extract_video_id(url)
