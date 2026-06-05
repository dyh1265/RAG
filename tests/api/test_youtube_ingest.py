"""API tests for POST /ingest/youtube/stream."""

from __future__ import annotations

import json
import re
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

from backend.api.dependencies import get_app_settings
from backend.api.main import app
from backend.core.models import QueryResponse
from backend.core.pipeline import IngestResult
from backend.video.youtube_ingestor import YouTubeIngestResult


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in re.split(r"\n\n+", text.strip()):
        if not block or block.startswith(":"):
            continue
        event_name = "message"
        data = ""
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                data = line[6:]
        if data:
            events.append((event_name, json.loads(data)))
    return events


@pytest.fixture
def client():
    pipeline = MagicMock()
    pipeline.config.block_forbidden_classifications = False
    pipeline.query.return_value = QueryResponse(query="q", answer="a")
    pipeline.index_chunks.return_value = IngestResult(
        doc_id="yt_doc_1",
        source_path="youtube:abc123xyz01",
        chunk_count=2,
        chunks_by_type={"transcript": 2},
        vectors_by_collection={"text_chunks": 2},
    )

    mock_settings = MagicMock()
    mock_settings.youtube_ingest_enabled = True

    with TestClient(app) as test_client:
        test_client.app.state.pipeline = pipeline
        test_client.app.dependency_overrides[get_app_settings] = lambda: mock_settings
        yield test_client
    app.dependency_overrides.pop(get_app_settings, None)


def test_youtube_stream_returns_progress_and_done(client):
    result = YouTubeIngestResult(
        ingest=client.app.state.pipeline.index_chunks.return_value,
        video_id="abc123xyz01",
        title="Test Lecture",
    )

    with patch(
        "backend.api.routers.youtube.YouTubeIngestor"
    ) as mock_cls:
        mock_cls.return_value.ingest.return_value = result
        response = client.post(
            "/ingest/youtube/stream",
            json={
                "url": "https://www.youtube.com/watch?v=abc123xyz01",
                "include_transcript": True,
                "include_slides": False,
            },
        )

    assert response.status_code == 200
    events = _parse_sse(response.text)
    kinds = [e[0] for e in events]
    assert "progress" in kinds
    assert "done" in kinds
    done_payload = next(data for kind, data in events if kind == "done")
    assert done_payload["doc_id"] == "yt_doc_1"
    assert done_payload["video_id"] == "abc123xyz01"
    assert done_payload["title"] == "Test Lecture"


def test_youtube_stream_handles_invalid_url(client):
    with patch(
        "backend.api.routers.youtube.YouTubeIngestor"
    ) as mock_cls:
        mock_cls.return_value.ingest.side_effect = ValueError("Not a YouTube URL")
        response = client.post(
            "/ingest/youtube/stream",
            json={"url": "https://example.com/not-youtube"},
        )

    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert any(kind == "error" for kind, _ in events)


def test_youtube_stream_handles_transcription_failure(client):
    with patch(
        "backend.api.routers.youtube.YouTubeIngestor"
    ) as mock_cls:
        mock_cls.return_value.ingest.side_effect = RuntimeError("Transcription failed")
        response = client.post(
            "/ingest/youtube/stream",
            json={"url": "https://www.youtube.com/watch?v=abc123xyz01"},
        )

    assert response.status_code == 200
    events = _parse_sse(response.text)
    error_events = [data for kind, data in events if kind == "error"]
    assert error_events
    assert "Transcription failed" in error_events[0]["message"]


def test_youtube_stream_disabled_returns_503(client):
    client.app.dependency_overrides[get_app_settings] = lambda: MagicMock(
        youtube_ingest_enabled=False
    )
    response = client.post(
        "/ingest/youtube/stream",
        json={"url": "https://www.youtube.com/watch?v=abc123xyz01"},
    )
    assert response.status_code == 503
