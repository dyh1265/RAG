"""Signed, stateless session tokens for per-user document isolation.

Anonymous demo visitors get an unguessable tenant id wrapped in an
HMAC-signed token. The signature makes the token unforgeable: a client can
only ever access documents under the tenant id embedded in a token that this
server actually issued, so isolation does not rely on the client behaving.

The token is intentionally simple (``<payload>.<sig>``, both base64url) to
avoid pulling in a JWT dependency. It carries only a tenant id and an
issued-at timestamp — there is no PII to protect.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from backend.core.config import get_settings


def _secret() -> bytes:
    return get_settings().session_secret.encode("utf-8")


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(body: str) -> str:
    digest = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def new_tenant_id() -> str:
    """Generate a fresh, unguessable tenant id."""
    return secrets.token_hex(16)


def mint_token(tenant_id: str) -> str:
    """Create a signed token that grants access to ``tenant_id``'s documents."""
    payload = {"t": tenant_id, "iat": int(time.time())}
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(body)}"


def verify_token(token: str) -> str | None:
    """Return the tenant id for a valid token, or ``None`` if invalid/expired."""
    try:
        body, signature = token.split(".", 1)
    except ValueError:
        return None

    if not hmac.compare_digest(signature, _sign(body)):
        return None

    try:
        payload = json.loads(_b64decode(body))
    except (ValueError, json.JSONDecodeError):
        return None

    tenant_id = payload.get("t")
    if not isinstance(tenant_id, str) or not tenant_id:
        return None

    max_age = get_settings().session_max_age_seconds
    if max_age > 0:
        issued_at = payload.get("iat")
        if not isinstance(issued_at, (int, float)):
            return None
        if time.time() - issued_at > max_age:
            return None

    return tenant_id
