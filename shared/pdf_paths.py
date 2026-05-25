"""Collect PDF paths from directories and globs."""

from __future__ import annotations

import glob
from pathlib import Path


def collect_pdf_paths(
    *,
    directory: str | Path | None = None,
    recursive: bool = True,
    patterns: list[str] | None = None,
    glob_pattern: str | None = None,
) -> list[Path]:
    """Return sorted unique PDF paths from a directory and/or glob patterns."""
    paths: set[Path] = set()

    if directory is not None:
        root = Path(directory)
        if not root.is_dir():
            raise FileNotFoundError(f"Not a directory: {root}")
        iterator = root.rglob("*.pdf") if recursive else root.glob("*.pdf")
        for path in iterator:
            if path.is_file() and path.suffix.lower() == ".pdf":
                paths.add(path.resolve())

    for pattern in patterns or []:
        for match in glob.glob(pattern, recursive=recursive):
            path = Path(match)
            if path.is_file() and path.suffix.lower() == ".pdf":
                paths.add(path.resolve())

    if glob_pattern:
        for match in glob.glob(glob_pattern, recursive=recursive):
            path = Path(match)
            if path.is_file() and path.suffix.lower() == ".pdf":
                paths.add(path.resolve())

    return sorted(paths)


def resolve_under_base(path: str | Path, base: Path) -> Path:
    """Resolve path and ensure it stays under base (prevents path traversal)."""
    base = base.resolve()
    candidate = Path(path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        from_cwd = (Path.cwd() / candidate).resolve()
        from_base = (base / candidate).resolve()
        if base in from_cwd.parents or from_cwd == base:
            resolved = from_cwd
        else:
            resolved = from_base
    if resolved != base and base not in resolved.parents:
        raise ValueError(f"path must be under {base}")
    return resolved
