"""HTTP client for DocuMind → Phase 6 rag-api."""

from __future__ import annotations

from pathlib import Path

import httpx

from shared.models import QueryResponse
from shared.pipeline import IngestResult


class DocuMindApiClient:
    def __init__(self, base_url: str, *, timeout: float = 300.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def ingest(self, path: Path) -> IngestResult:
        with path.open("rb") as fh:
            response = httpx.post(
                f"{self.base_url}/ingest",
                files={"file": (path.name, fh, "application/pdf")},
                timeout=self.timeout,
            )
        response.raise_for_status()
        data = response.json()
        return IngestResult(
            doc_id=data["doc_id"],
            source_path=data["source_path"],
            chunk_count=data["chunk_count"],
            chunks_by_type=data.get("chunks_by_type", {}),
            vectors_by_collection=data.get("vectors_by_collection", {}),
            errors=data.get("errors", []),
            skipped=data.get("skipped", False),
        )

    def ask(
        self,
        query: str,
        *,
        doc_id: str,
        top_k: int = 5,
        provider: str = "openai",
        retrieve_only: bool = False,
        block_forbidden: bool | None = None,
    ) -> QueryResponse:
        payload: dict = {
            "query": query,
            "doc_id": doc_id,
            "top_k": top_k,
            "provider": provider,
            "retrieve_only": retrieve_only,
        }
        if block_forbidden is not None:
            payload["block_forbidden"] = block_forbidden

        response = httpx.post(
            f"{self.base_url}/query",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return QueryResponse.model_validate(response.json())

    def ingest_directory(
        self,
        directory: str,
        *,
        recursive: bool = True,
    ) -> dict:
        response = httpx.post(
            f"{self.base_url}/ingest/directory",
            json={"directory": directory, "recursive": recursive},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
