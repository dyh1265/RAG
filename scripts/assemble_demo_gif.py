"""Assemble docs/images/demo_frames/*.png into docs/images/demo.gif."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FRAMES_DIR = ROOT / "docs" / "images" / "demo_frames"
OUT_GIF = ROOT / "docs" / "images" / "demo.gif"
TARGET_SIZE = (1280, 800)
MAX_BYTES = 5 * 1024 * 1024


def load_frames() -> list[Image.Image]:
    paths = sorted(FRAMES_DIR.glob("*.png"))
    if not paths:
        raise SystemExit(f"No PNG frames in {FRAMES_DIR}")
    frames: list[Image.Image] = []
    for path in paths:
        img = Image.open(path).convert("RGB")
        if img.size != TARGET_SIZE:
            img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        frames.append(img)
    return frames


def save_gif(frames: list[Image.Image], duration_ms: int, colors: int) -> int:
    OUT_GIF.parent.mkdir(parents=True, exist_ok=True)
    palette_frames = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors) for f in frames]
    palette_frames[0].save(
        OUT_GIF,
        save_all=True,
        append_images=palette_frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    return OUT_GIF.stat().st_size


def main() -> None:
    frames = load_frames()
    # Hold landing/answer a bit longer for readability.
    hold = [0, 1, -1]  # duplicate first, second-to-last pacing via duration
    expanded: list[Image.Image] = []
    for i, f in enumerate(frames):
        expanded.append(f)
        if i in hold:
            expanded.append(f)

    for duration_ms, colors in [(900, 128), (700, 96), (500, 64)]:
        size = save_gif(expanded, duration_ms=duration_ms, colors=colors)
        print(f"demo.gif: {size / 1024:.1f} KB ({len(expanded)} frames, {duration_ms}ms, {colors} colors)")
        if size <= MAX_BYTES:
            return

    print(f"Warning: GIF is {OUT_GIF.stat().st_size / 1024:.1f} KB (> {MAX_BYTES // 1024} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
