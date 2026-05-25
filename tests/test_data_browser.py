"""Tests for data directory browser."""

from __future__ import annotations

from pathlib import Path

from backend.core.data_browser import browse_directory


def test_browse_lists_dirs_and_pdfs(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "data" / "raw"
    apps = base / "applications"
    apps.mkdir(parents=True)
    (apps / "cv.pdf").write_bytes(b"%PDF")
    (base / "readme.txt").write_text("skip")

    listing = browse_directory(base)
    names = [e.name for e in listing.entries]
    assert "applications" in names
    assert "readme.txt" not in names

    nested = browse_directory(base, "data/raw/applications")
    assert any(e.name == "cv.pdf" and e.pdf for e in nested.entries)
