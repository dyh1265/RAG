"""Tests for Prometheus metrics startup."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from phases.phase_03_scalable_ingestion.monitoring import metrics


def test_start_metrics_server_swallows_addr_in_use(monkeypatch):
    monkeypatch.setattr(metrics, "_server_started", False)
    with patch.object(metrics, "start_http_server", side_effect=OSError(98, "Address already in use")):
        metrics.start_metrics_server(port=59999)
    assert metrics._server_started is True


def test_start_metrics_server_idempotent(monkeypatch):
    monkeypatch.setattr(metrics, "_server_started", True)
    mock_start = MagicMock()
    with patch.object(metrics, "start_http_server", mock_start):
        metrics.start_metrics_server(port=59998)
    mock_start.assert_not_called()
