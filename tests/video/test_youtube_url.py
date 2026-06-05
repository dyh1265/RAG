"""Tests for YouTube URL parsing."""

from __future__ import annotations

import pytest

from backend.video.youtube_url import (
    YouTubeURLError,
    canonical_watch_url,
    extract_video_id,
    timestamp_url,
    validate_youtube_url,
)

VIDEO_ID = "dQw4w9WgXcQ"


def test_extracts_video_id_from_watch_url():
    assert extract_video_id(f"https://www.youtube.com/watch?v={VIDEO_ID}") == VIDEO_ID


def test_extracts_video_id_from_youtu_be():
    assert extract_video_id(f"https://youtu.be/{VIDEO_ID}") == VIDEO_ID


def test_extracts_video_id_from_shorts():
    assert extract_video_id(f"https://www.youtube.com/shorts/{VIDEO_ID}") == VIDEO_ID


def test_rejects_non_youtube_url():
    with pytest.raises(YouTubeURLError):
        validate_youtube_url("https://example.com/watch?v=abc")


def test_builds_timestamp_url():
    url = timestamp_url(VIDEO_ID, 492)
    assert VIDEO_ID in url
    assert "t=492s" in url


def test_canonical_watch_url():
    assert canonical_watch_url(VIDEO_ID) == f"https://www.youtube.com/watch?v={VIDEO_ID}"
