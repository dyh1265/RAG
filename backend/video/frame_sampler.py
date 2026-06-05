"""Sample frames from a video file at a fixed time interval."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class FrameSamplingError(RuntimeError):
    """Raised when OpenCV cannot read or sample a video file."""


@dataclass(frozen=True)
class SampledFrame:
    image_path: Path
    timestamp: float


def sample_frames(
    video_path: Path,
    out_dir: Path,
    *,
    sample_every_seconds: float = 2.0,
) -> list[SampledFrame]:
    """Extract JPEG frames every ``sample_every_seconds`` from a video file."""
    try:
        import cv2
    except ImportError as exc:
        raise FrameSamplingError(
            "opencv-python-headless is not installed. "
            "Install with: pip install opencv-python-headless"
        ) from exc

    if not video_path.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise FrameSamplingError(f"Could not open video: {video_path}")

    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        if fps <= 0:
            fps = 25.0
        frame_interval = max(1, int(round(fps * sample_every_seconds)))

        sampled: list[SampledFrame] = []
        frame_index = 0
        saved = 0

        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index % frame_interval == 0:
                timestamp = frame_index / fps
                image_path = out_dir / f"frame_{saved:05d}.jpg"
                if not cv2.imwrite(str(image_path), frame):
                    raise FrameSamplingError(f"Failed to write frame image: {image_path}")
                sampled.append(SampledFrame(image_path=image_path, timestamp=timestamp))
                saved += 1
            frame_index += 1

        return sampled
    finally:
        capture.release()
