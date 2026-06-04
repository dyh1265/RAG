"""Session endpoint — issues a signed token that scopes a browser's documents."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.rate_limit import limiter, rate_limit
from backend.api.sessions import mint_token, new_tenant_id

router = APIRouter()


@router.post("")
@limiter.limit(rate_limit())
async def create_session(request: Request) -> dict:
    """Mint a fresh anonymous session for a new visitor.

    The client persists the returned ``token`` and sends it as
    ``Authorization: Bearer <token>`` on every subsequent request. Possession
    of the token is what grants access to that tenant's documents, so the
    client should keep it private and reuse it across reloads.
    """
    tenant_id = new_tenant_id()
    return {"token": mint_token(tenant_id), "tenant_id": tenant_id}
