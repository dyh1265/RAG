"""Detect unique slide frames by removing near-duplicate sampled images."""

from __future__ import annotations

import shutil
from pathlib import Path

import imagehash
from PIL import Image

from backend.video.frame_sampler import SampledFrame
from backend.video.models import SlideFrame


def detect_unique_slides(
    frames: list[SampledFrame],
    *,
    slides_dir: Path,
    max_hamming_distance: int = 8,
) -> list[SlideFrame]:
    """Keep visually distinct frames; assign monotonic slide numbers in time order."""
    slides_dir.mkdir(parents=True, exist_ok=True)
    if not frames:
        return []

    unique: list[SlideFrame] = []
    last_hash: imagehash.ImageHash | None = None

    for frame in frames:
        if not frame.image_path.is_file():
            continue

        with Image.open(frame.image_path) as img:
            frame_hash = imagehash.phash(img.convert("RGB"))

        if last_hash is not None and (frame_hash - last_hash) <= max_hamming_distance:
            continue

        slide_number = len(unique) + 1
        dest = slides_dir / f"slide_{slide_number:03d}.png"
        shutil.copy2(frame.image_path, dest)
        unique.append(
            SlideFrame(
                image_path=dest,
                timestamp=frame.timestamp,
                slide_number=slide_number,
            )
        )
        last_hash = frame_hash

    return unique
