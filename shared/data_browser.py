"""Browse directories under the raw documents root."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.pdf_paths import resolve_under_base


@dataclass
class DirectoryEntry:
    name: str
    path: str
    kind: str  # "directory" | "file"
    pdf: bool = False


@dataclass
class DirectoryListing:
    path: str
    parent: str | None
    entries: list[DirectoryEntry]


def _display_path(resolved: Path, base: Path) -> str:
    """Project-style path string for API responses."""
    try:
        rel = resolved.relative_to(Path.cwd().resolve())
        return rel.as_posix()
    except ValueError:
        try:
            rel = resolved.relative_to(base)
            return (base.name + "/" + rel.as_posix()).replace("//", "/")
        except ValueError:
            return resolved.as_posix()


def browse_directory(
    base: Path,
    path: str | None = None,
) -> DirectoryListing:
    """List subdirectories and PDF files under base (or a subpath)."""
    base = base.resolve()
    target = resolve_under_base(path or ".", base) if path else base
    if not target.is_dir():
        raise FileNotFoundError(f"Not a directory: {target}")

    entries: list[DirectoryEntry] = []
    for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name.startswith("."):
            continue
        resolved = child.resolve()
        rel_path = _display_path(resolved, base)
        if child.is_dir():
            entries.append(DirectoryEntry(name=child.name, path=rel_path, kind="directory"))
        elif child.suffix.lower() == ".pdf":
            entries.append(
                DirectoryEntry(name=child.name, path=rel_path, kind="file", pdf=True)
            )

    parent: str | None = None
    if target != base:
        parent = _display_path(target.parent, base)

    return DirectoryListing(
        path=_display_path(target, base),
        parent=parent,
        entries=entries,
    )
