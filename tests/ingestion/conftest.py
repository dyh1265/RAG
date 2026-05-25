"""Shared fixtures for ingestion unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_pdf_path():
    path = Path(__file__).resolve().parents[2] / "data" / "raw" / "sample_report.pdf"
    if not path.exists():
        pytest.skip("sample_report.pdf not found — run scripts/generate_sample_report.py")
    return path
