"""Tests for ingest mode parser selection."""

from __future__ import annotations

from backend.scaling.pipeline.ingest_modes import IngestMode, build_ingestion_pipeline


def test_text_only_has_two_parsers():
    pipeline = build_ingestion_pipeline(IngestMode.TEXT_ONLY)
    assert len(pipeline.parsers) == 2


def test_full_has_four_parsers():
    pipeline = build_ingestion_pipeline(IngestMode.FULL)
    assert len(pipeline.parsers) == 4
