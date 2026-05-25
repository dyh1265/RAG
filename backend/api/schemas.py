"""HTTP request/response schemas for the production API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.core.models import Citation, QueryResponse, RetrievedContext


class QueryBody(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=50)
    doc_id: str | None = None
    provider: str = "ollama"
    retrieve_only: bool = False
    block_forbidden: bool | None = None


class QueryResponseOut(BaseModel):
    query: str
    answer: str
    citations: list[Citation]
    retrieved_contexts: list[RetrievedContext]
    model_used: str | None = None
    latency_ms: float | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    pii_redacted: bool = False

    @classmethod
    def from_pipeline(cls, response: QueryResponse, *, pii_redacted: bool = False) -> QueryResponseOut:
        return cls(
            query=response.query,
            answer=response.answer,
            citations=response.citations,
            retrieved_contexts=response.retrieved_contexts,
            model_used=response.model_used,
            latency_ms=response.latency_ms,
            session_id=response.session_id,
            metadata=response.metadata,
            pii_redacted=pii_redacted,
        )


class IngestResponseOut(BaseModel):
    doc_id: str
    source_path: str
    chunk_count: int
    chunks_by_type: dict[str, int]
    vectors_by_collection: dict[str, int]
    errors: list[str] = Field(default_factory=list)
    skipped: bool = False


class DirectoryIngestBody(BaseModel):
    directory: str = Field(description="Path under data/raw (e.g. data/raw/applications)")
    recursive: bool = True


class DirectoryIngestOut(BaseModel):
    directory: str
    total_files: int
    ingested: int
    skipped: int
    failed: int
    documents: list[IngestResponseOut] = Field(default_factory=list)


class BulkIngestStartBody(BaseModel):
    folder_name: str = Field(min_length=1, max_length=256)
    total_files: int = Field(ge=1, le=5000)


class BulkIngestStartOut(BaseModel):
    job_id: str
    total_files: int


class BulkIngestUploadOut(BaseModel):
    job_id: str
    uploaded: int
    total: int
    filename: str


class BulkIngestRunOut(BaseModel):
    job_id: str
    queued: int
    status: str


class BulkIngestJobOut(BaseModel):
    job_id: str
    folder_name: str
    status: str
    total: int
    uploaded: int
    processed: int
    ingested: int
    skipped: int
    failed: int
    current_file: str | None = None
    message: str | None = None


class CollectionStatsOut(BaseModel):
    name: str
    points_count: int | None = None
    vector_size: int | None = None


class DocumentSummaryOut(BaseModel):
    doc_id: str
    name: str
    source_path: str = ""
    chunk_count: int = 0


class DocumentSuggestionsOut(BaseModel):
    doc_id: str
    questions: list[str] = Field(default_factory=list)


class DirectoryEntryOut(BaseModel):
    name: str
    path: str
    kind: str
    pdf: bool = False


class DirectoryBrowseOut(BaseModel):
    path: str
    parent: str | None = None
    entries: list[DirectoryEntryOut] = Field(default_factory=list)
