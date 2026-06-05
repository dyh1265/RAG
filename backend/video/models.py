"""Internal models for YouTube video ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class YouTubeVideoInfo:
    video_id: str
    title: str
    url: str
    duration_seconds: float | None
    work_dir: Path


@dataclass
class TranscriptSegment:
    text: str
    start: float
    end: float


@dataclass
class SlideFrame:
    image_path: Path
    timestamp: float
    slide_number: int
