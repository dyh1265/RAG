"""Tests for Redis-backed bulk ingest job tracking."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.scaling.jobs.bulk_job_store import BulkJobStore


@pytest.fixture
def job_store():
    backing: dict[str, str] = {}
    client = MagicMock()
    client.ping = MagicMock(return_value=True)
    client.setex = lambda key, ttl, value: backing.__setitem__(key, value)
    client.get = lambda key: backing.get(key)
    store = BulkJobStore(redis_url="redis://fake/0")
    store._client = client
    return store


def test_bulk_job_lifecycle(job_store: BulkJobStore):
    job_store.create("job1", folder_name="PhD", total=2)
    job_store.add_uploaded_path("job1", "/data/a.pdf", "a.pdf")
    job_store.add_uploaded_path("job1", "/data/b.pdf", "b.pdf")
    job_store.mark_queued("job1")
    job_store.mark_running("job1")
    job_store.record_task_result(
        "job1",
        {"path": "/data/a.pdf", "status": "success", "chunk_count": 5, "errors": []},
    )
    job = job_store.record_task_result(
        "job1",
        {"path": "/data/b.pdf", "status": "skipped", "chunk_count": 0, "errors": []},
    )

    assert job.status == "done"
    assert job.ingested == 1
    assert job.skipped == 1
    assert job.failed == 0


def test_pending_paths(job_store: BulkJobStore):
    job_store.create("job2", folder_name="Internship", total=3)
    job_store.add_uploaded_path("job2", "/data/a.pdf", "a.pdf")
    job_store.add_uploaded_path("job2", "/data/b.pdf", "b.pdf")
    job_store.add_uploaded_path("job2", "/data/c.pdf", "c.pdf")
    job_store.mark_queued("job2")
    job_store.mark_running("job2")
    job_store.record_task_result(
        "job2",
        {"path": "/data/a.pdf", "status": "success", "chunk_count": 1, "errors": []},
    )
    job = job_store.get("job2")
    assert job is not None
    assert job.pending_paths() == ["/data/b.pdf", "/data/c.pdf"]
    assert job.completed_paths() == {"/data/a.pdf"}


def test_duplicate_path_replaces_instead_of_double_counting(job_store: BulkJobStore):
    job_store.create("job3", folder_name="PhD", total=1)
    job_store.add_uploaded_path("job3", "/data/a.pdf", "a.pdf")
    job_store.mark_queued("job3")
    job_store.mark_running("job3")
    job_store.record_task_result(
        "job3",
        {"path": "/data/a.pdf", "status": "success", "chunk_count": 3, "errors": []},
    )
    job = job_store.record_task_result(
        "job3",
        {"path": "/data/a.pdf", "status": "skipped", "chunk_count": 0, "errors": []},
    )

    assert job.processed == 1
    assert job.ingested == 0
    assert job.skipped == 1
    assert job.failed == 0
    assert job.status == "done"
    assert len(job.results) == 1
