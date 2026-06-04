"""Unit tests for signed session tokens."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock

import pytest

from backend.api.sessions import (
    _b64decode,
    _sign,
    mint_token,
    new_tenant_id,
    verify_token,
)
from backend.core.config import Settings, get_settings


@pytest.fixture
def session_settings(monkeypatch):
    """Fixed secret and max-age for deterministic token tests."""
    settings = Settings.model_construct(
        session_secret="unit-test-session-secret",
        session_max_age_seconds=3600,
    )
    monkeypatch.setattr("backend.api.sessions.get_settings", lambda: settings)
    get_settings.cache_clear()
    yield settings
    get_settings.cache_clear()


def test_new_tenant_id_is_hex_and_unique():
    a = new_tenant_id()
    b = new_tenant_id()
    assert len(a) == 32
    assert all(c in "0123456789abcdef" for c in a)
    assert a != b


def test_mint_and_verify_roundtrip(session_settings):
    tenant = "abc123tenant"
    token = mint_token(tenant)
    assert verify_token(token) == tenant


def test_verify_rejects_tampered_signature(session_settings):
    token = mint_token("tenant-a")
    body, sig = token.split(".", 1)
    assert verify_token(f"{body}.{sig}x") is None


def test_verify_rejects_tampered_payload(session_settings):
    token = mint_token("tenant-a")
    body, sig = token.split(".", 1)
    payload = json.loads(_b64decode(body))
    payload["t"] = "other-tenant"
    from backend.api.sessions import _b64encode

    forged_body = _b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    assert verify_token(f"{forged_body}.{sig}") is None


def test_verify_rejects_garbage_token(session_settings):
    assert verify_token("") is None
    assert verify_token("not-a-token") is None
    assert verify_token("onlyonepart") is None


def test_verify_rejects_expired_token(session_settings, monkeypatch):
    tenant = "expired-tenant"
    token = mint_token(tenant)
    assert verify_token(token) == tenant

    future = time.time() + session_settings.session_max_age_seconds + 1
    monkeypatch.setattr("backend.api.sessions.time.time", lambda: future)
    assert verify_token(token) is None


def test_verify_accepts_token_when_max_age_zero(monkeypatch):
    settings = Settings.model_construct(
        session_secret="unit-test-session-secret",
        session_max_age_seconds=0,
    )
    monkeypatch.setattr("backend.api.sessions.get_settings", lambda: settings)
    issued_at = 1_700_000_000
    monkeypatch.setattr("backend.api.sessions.time.time", lambda: issued_at)
    tenant = "no-expiry"
    token = mint_token(tenant)
    monkeypatch.setattr(
        "backend.api.sessions.time.time",
        lambda: issued_at + 999_999_999,
    )
    assert verify_token(token) == tenant


def test_verify_rejects_empty_tenant_in_payload(session_settings):
    token = mint_token("ok")
    body, _ = token.split(".", 1)
    payload = json.loads(_b64decode(body))
    payload["t"] = ""
    from backend.api.sessions import _b64encode

    bad_body = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    assert verify_token(f"{bad_body}.{_sign(bad_body)}") is None


def test_verify_rejects_wrong_secret(session_settings, monkeypatch):
    token = mint_token("tenant-a")
    other = Settings.model_construct(
        session_secret="different-secret-from-unit-test",
        session_max_age_seconds=3600,
    )
    monkeypatch.setattr("backend.api.sessions.get_settings", lambda: other)
    assert verify_token(token) is None
