"""Bulk ingest, caching, and async workers (wraps ``phases.phase_03_scalable_ingestion/``)."""

from phases.phase_03_scalable_ingestion.pipeline.ingest_modes import IngestMode, build_ingestion_pipeline

__all__ = ["IngestMode", "build_ingestion_pipeline"]
