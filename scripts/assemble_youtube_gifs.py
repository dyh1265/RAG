"""Assemble YouTube demo frames into two GIFs.

  docs/images/yt_frames/ingest/*.png -> docs/images/demo_youtube_ingest.gif
  docs/images/yt_frames/qa/*.png     -> docs/images/demo_youtube_qa.gif
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FRAMES_ROOT = ROOT / "docs" / "images" / "yt_frames"
IMAGES_DIR = ROOT / "docs" / "images"
TARGET_SIZE = (1280, 800)
MAX_BYTES = 5 * 1024 * 1024

JOBS = [
    ("ingest", IMAGES_DIR / "demo_youtube_ingest.gif"),
    ("qa", IMAGES_DIR / "demo_youtube_qa.gif"),
]


def load_frames(sub: str) -> list[Image.Image]:
    paths = sorted((FRAMES_ROOT / sub).glob("*.png"))
    frames: list[Image.Image] = []
    for path in paths:
        img = Image.open(path).convert("RGB")
        if img.size != TARGET_SIZE:
            img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        frames.append(img)
    return frames


def save_gif(out: Path, frames: list[Image.Image], duration_ms: int, colors: int) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    palette = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors) for f in frames]
    palette[0].save(
        out,
        save_all=True,
        append_images=palette[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    return out.stat().st_size


def build(sub: str, out: Path) -> None:
    frames = load_frames(sub)
    if not frames:
        print(f"skip {out.name}: no frames in {FRAMES_ROOT / sub}", file=sys.stderr)
        return
    # Hold the first and last frame a touch longer for readability.
    expanded = [frames[0], *frames, frames[-1]]
    for duration_ms, colors in [(1100, 128), (900, 96), (700, 64)]:
        size = save_gif(out, expanded, duration_ms=duration_ms, colors=colors)
        print(f"{out.name}: {size / 1024:.1f} KB ({len(expanded)} frames, {duration_ms}ms, {colors} colors)")
        if size <= MAX_BYTES:
            return
    print(f"Warning: {out.name} is {out.stat().st_size / 1024:.1f} KB (> {MAX_BYTES // 1024} KB)", file=sys.stderr)


def main() -> None:
    for sub, out in JOBS:
        build(sub, out)


if __name__ == "__main__":
    main()
