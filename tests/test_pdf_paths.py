"""Tests for PDF path collection."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.pdf_paths import collect_pdf_paths, resolve_under_base


def test_collect_pdf_paths_from_directory(tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    (tmp_path / "b.txt").write_text("nope")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.pdf").write_bytes(b"%PDF")

    flat = collect_pdf_paths(directory=tmp_path, recursive=False)
    assert [p.name for p in flat] == ["a.pdf"]

    deep = collect_pdf_paths(directory=tmp_path, recursive=True)
    assert sorted(p.name for p in deep) == ["a.pdf", "c.pdf"]


def test_resolve_under_base_blocks_traversal(tmp_path: Path):
    base = tmp_path / "data" / "raw"
    base.mkdir(parents=True)
    with pytest.raises(ValueError):
        resolve_under_base("../../etc", base)

    inner = base / "apps"
    inner.mkdir()
    assert resolve_under_base("apps", base) == inner.resolve()
