"""API tests for signed-session tenant isolation and bulk job ownership."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")
# Full API tests need the same runtime deps as tests/api/test_api.py (CI/dev image).
pytest.importorskip("fitz")
pytest.importorskip("torch")

from backend.api.dependencies import DEFAULT_TENANT
from backend.api.sessions import mint_token
from backend.core.config import Settings, get_settings
from backend.core.models import QueryResponse
from backend.api.main import app
from backend.scaling.jobs.bulk_job_store import BulkJobStore


@pytest.fixture
def session_settings(monkeypatch):
    settings = Settings(
        session_secret="api-test-session-secret",
        session_max_age_seconds=86_400,
    )
    monkeypatch.setattr("backend.api.sessions.get_settings", lambda: settings)
    monkeypatch.setattr("backend.api.dependencies.get_settings", lambda: settings)
    get_settings.cache_clear()
    yield settings
    get_settings.cache_clear()


@pytest.fixture
def client(session_settings):
    pipeline = MagicMock()
    pipeline.config.block_forbidden_classifications = False
    pipeline.query.return_value = QueryResponse(query="q", answer="a")
    pipeline.store.list_documents.return_value = []
    with TestClient(app) as test_client:
        test_client.app.state.pipeline = pipeline
        yield test_client


def _auth(tenant_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_token(tenant_id)}"}


def test_create_session_returns_signed_token(client):
    response = client.post("/session")
    assert response.status_code == 200
    body = response.json()
    assert "token" in body
    assert "tenant_id" in body
    assert len(body["tenant_id"]) == 32
    assert verify_token_from_response(body["token"], body["tenant_id"])


def verify_token_from_response(token: str, expected_tenant: str) -> bool:
    from backend.api.sessions import verify_token

    return verify_token(token) == expected_tenant


def test_list_documents_without_token_uses_public_tenant(client):
    client.get("/admin/documents")
    client.app.state.pipeline.store.list_documents.assert_called_with(
        limit=100, tenant_id=DEFAULT_TENANT
    )


def test_list_documents_with_bearer_scopes_to_tenant(client):
    tenant = "user-tenant-aaa111"
    client.get("/admin/documents", headers=_auth(tenant))
    client.app.state.pipeline.store.list_documents.assert_called_with(
        limit=100, tenant_id=tenant
    )


def test_invalid_bearer_returns_401(client):
    response = client.get(
        "/admin/documents",
        headers={"Authorization": "Bearer not.valid.token"},
    )
    assert response.status_code == 401
    assert "session" in response.json()["detail"].lower()


def test_query_injects_tenant_filter(client):
    tenant = "query-tenant-bbb222"
    client.post(
        "/query",
        json={"query": "What is revenue?", "doc_id": "doc1", "retrieve_only": True},
        headers=_auth(tenant),
    )
    call_args = client.app.state.pipeline.query.call_args
    request = call_args[0][0]
    assert request.filters["tenant_id"] == tenant
    assert request.filters["doc_id"] == "doc1"


def test_document_preview_accepts_token_query_param(client, tmp_path):
    tenant = "preview-tenant-ccc333"
    token = mint_token(tenant)
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    from backend.api.dependencies import get_app_settings

    mock_settings = MagicMock()
    mock_settings.data_dir = str(tmp_path)
    mock_settings.raw_docs_dir = str(tmp_path)
    client.app.dependency_overrides[get_app_settings] = lambda: mock_settings
    client.app.state.pipeline.store.get_document_source_path.return_value = str(
        pdf_path
    )

    try:
        response = client.get(
            f"/admin/documents/doc123/file?t={token}",
        )
        assert response.status_code == 200
        client.app.state.pipeline.store.get_document_source_path.assert_called_with(
            "doc123", tenant_id=tenant
        )
    finally:
        client.app.dependency_overrides.pop(get_app_settings, None)


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


def test_bulk_status_404_when_accessing_another_tenants_job(
    client, bulk_job_store, monkeypatch, tmp_path
):
    bulk_job_store.create("job-cross", folder_name="F", total=1, tenant_id="tenant-a")
    monkeypatch.setattr(
        "backend.api.routers.bulk_ingest.BulkJobStore",
        lambda *args, **kwargs: bulk_job_store,
    )

    response = client.get(
        "/ingest/bulk/job-cross",
        headers=_auth("tenant-b"),
    )
    assert response.status_code == 404


def test_bulk_status_ok_for_owner(client, bulk_job_store, monkeypatch):
    bulk_job_store.create("job-mine", folder_name="F", total=1, tenant_id="tenant-a")
    monkeypatch.setattr(
        "backend.api.routers.bulk_ingest.BulkJobStore",
        lambda *args, **kwargs: bulk_job_store,
    )

    response = client.get(
        "/ingest/bulk/job-mine",
        headers=_auth("tenant-a"),
    )
    assert response.status_code == 200
    assert response.json()["job_id"] == "job-mine"


def test_bulk_start_stores_caller_tenant(client, bulk_job_store, monkeypatch, tmp_path):
    from backend.api.dependencies import get_app_settings

    mock_settings = MagicMock()
    mock_settings.raw_docs_dir = str(tmp_path / "raw")
    (tmp_path / "raw").mkdir()
    client.app.dependency_overrides[get_app_settings] = lambda: mock_settings
    monkeypatch.setattr(
        "backend.api.routers.bulk_ingest.BulkJobStore",
        lambda *args, **kwargs: bulk_job_store,
    )

    tenant = "bulk-starter-ddd444"
    try:
        response = client.post(
            "/ingest/bulk/start",
            json={"folder_name": "MyFolder", "total_files": 1},
            headers=_auth(tenant),
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        job = bulk_job_store.get(job_id)
        assert job is not None
        assert job.tenant_id == tenant
    finally:
        client.app.dependency_overrides.pop(get_app_settings, None)


def test_bulk_run_passes_tenant_in_task_options(
    client, bulk_job_store, monkeypatch, tmp_path
):
    from backend.api.dependencies import get_app_settings

    job_id = "run-job-1"
    tenant = "bulk-runner-eee555"
    bulk_job_store.create(job_id, folder_name="F", total=1, tenant_id=tenant)
    bulk_job_store.add_uploaded_path(job_id, str(tmp_path / "a.pdf"), "a.pdf")
    (tmp_path / "a.pdf").write_bytes(b"%PDF")

    mock_settings = MagicMock()
    mock_settings.raw_docs_dir = str(tmp_path)
    client.app.dependency_overrides[get_app_settings] = lambda: mock_settings
    monkeypatch.setattr(
        "backend.api.routers.bulk_ingest.BulkJobStore",
        lambda *args, **kwargs: bulk_job_store,
    )
    monkeypatch.setattr(
        "backend.api.routers.bulk_ingest.celery_workers_available",
        lambda timeout=2.0: True,
    )

    queued: list[dict] = []

    def capture_queue(paths, *, job_id=None, options=None):
        queued.append(options or {})
        return len(paths)

    monkeypatch.setattr(
        "backend.api.routers.bulk_ingest.queue_documents",
        capture_queue,
    )

    try:
        response = client.post(
            f"/ingest/bulk/{job_id}/run",
            headers=_auth(tenant),
        )
        assert response.status_code == 200
        assert queued[0]["tenant_id"] == tenant
    finally:
        client.app.dependency_overrides.pop(get_app_settings, None)
