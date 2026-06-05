"""Tests for slide frame deduplication."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw

from backend.video.frame_sampler import SampledFrame
from backend.video.slide_detector import detect_unique_slides


def _pattern_frame(path: Path, *, seed: int) -> None:
    """Build a frame with a distinct checkerboard pattern (phash-differentiable)."""
    img = Image.new("RGB", (320, 180), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    cell = 20 + (seed % 5) * 4
    color_a = (seed * 37 % 200, seed * 53 % 200, seed * 71 % 200)
    color_b = (255 - color_a[0], 255 - color_a[1], 255 - color_a[2])
    for y in range(0, 180, cell):
        for x in range(0, 320, cell):
            fill = color_a if ((x // cell) + (y // cell) + seed) % 2 == 0 else color_b
            draw.rectangle([x, y, x + cell, y + cell], fill=fill)
    img.save(path)


def test_near_duplicate_frames_are_removed(tmp_path: Path):
    frames_dir = tmp_path / "frames"
    slides_dir = tmp_path / "slides"
    frames_dir.mkdir()

    frame_a = frames_dir / "a.jpg"
    frame_b = frames_dir / "b.jpg"
    _pattern_frame(frame_a, seed=1)
    shutil.copy2(frame_a, frame_b)

    sampled = [
        SampledFrame(image_path=frame_a, timestamp=0.0),
        SampledFrame(image_path=frame_b, timestamp=2.0),
    ]
    slides = detect_unique_slides(sampled, slides_dir=slides_dir)
    assert len(slides) == 1


def test_visually_different_frames_are_kept(tmp_path: Path):
    frames_dir = tmp_path / "frames"
    slides_dir = tmp_path / "slides"
    frames_dir.mkdir()

    frame_a = frames_dir / "a.jpg"
    frame_b = frames_dir / "b.jpg"
    _pattern_frame(frame_a, seed=1)
    _pattern_frame(frame_b, seed=99)

    sampled = [
        SampledFrame(image_path=frame_a, timestamp=0.0),
        SampledFrame(image_path=frame_b, timestamp=2.0),
    ]
    slides = detect_unique_slides(sampled, slides_dir=slides_dir)
    assert len(slides) == 2


def test_slide_numbers_are_assigned_in_order(tmp_path: Path):
    frames_dir = tmp_path / "frames"
    slides_dir = tmp_path / "slides"
    frames_dir.mkdir()

    paths = []
    for idx in range(3):
        path = frames_dir / f"{idx}.jpg"
        _pattern_frame(path, seed=idx * 17 + 3)
        paths.append(path)

    sampled = [
        SampledFrame(image_path=paths[0], timestamp=0.0),
        SampledFrame(image_path=paths[1], timestamp=2.0),
        SampledFrame(image_path=paths[2], timestamp=4.0),
    ]
    slides = detect_unique_slides(sampled, slides_dir=slides_dir)
    assert [s.slide_number for s in slides] == [1, 2, 3]
    assert slides[0].timestamp == 0.0
    assert slides[-1].timestamp == 4.0
