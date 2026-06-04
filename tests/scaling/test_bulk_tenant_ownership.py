"""Bulk job tenant ownership (no FastAPI / ML stack required)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend.scaling.jobs.bulk_job_store import BulkJobStore


def _require_owned_job(store: BulkJobStore, job_id: str, tenant_id: str):
    """Mirror of backend.api.routers.bulk_ingest._require_owned_job."""
    job = store.get(job_id)
    if job is None or job.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Bulk job not found")
    return job


@pytest.fixture
def bulk_job_store():
    backing: dict[str, str] = {}
    redis_client = MagicMock()
    redis_client.ping = MagicMock(return_value=True)
    redis_client.setex = lambda key, ttl, value: backing.__setitem__(key, value)
    redis_client.get = lambda key: backing.get(key)
    store = BulkJobStore(redis_url="redis://fake/0")
    store._client = redis_client
    return store


def test_bulk_job_store_persists_tenant_id(bulk_job_store: BulkJobStore):
    bulk_job_store.create("job-tenant", folder_name="Docs", total=2, tenant_id="t-xyz")
    job = bulk_job_store.get("job-tenant")
    assert job is not None
    assert job.tenant_id == "t-xyz"


def test_require_owned_job_returns_job_for_matching_tenant(bulk_job_store: BulkJobStore):
    bulk_job_store.create("owned", folder_name="X", total=1, tenant_id="owner-1")
    job = _require_owned_job(bulk_job_store, "owned", "owner-1")
    assert job.job_id == "owned"


def test_require_owned_job_404_for_wrong_tenant(bulk_job_store: BulkJobStore):
    bulk_job_store.create("secret", folder_name="X", total=1, tenant_id="owner-a")
    with pytest.raises(HTTPException) as exc:
        _require_owned_job(bulk_job_store, "secret", "owner-b")
    assert exc.value.status_code == 404


def test_require_owned_job_404_for_missing_job(bulk_job_store: BulkJobStore):
    with pytest.raises(HTTPException) as exc:
        _require_owned_job(bulk_job_store, "nope", "any")
    assert exc.value.status_code == 404
