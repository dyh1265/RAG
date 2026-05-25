"""
Pydantic data models shared across the backend.
These define the core data contracts that flow through the entire pipeline.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ChunkType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    FIGURE = "figure"
    PAGE_IMAGE = "page_image"
    HEADING = "heading"


class DocumentType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    IMAGE = "image"
    HTML = "html"


class RetrievalStrategy(str, Enum):
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"
    COLPALI = "colpali"


# ---------------------------------------------------------------------------
# Core chunk model — the atom that flows through ingestion → retrieval
# ---------------------------------------------------------------------------

class BoundingBox(BaseModel):
    """Page-relative bounding box in normalised [0,1] coordinates."""
    x0: float
    y0: float
    x1: float
    y1: float
    page: int


class DocumentChunk(BaseModel):
    """
    A single unit of content extracted from a source document.
    Produced by parsers and consumed by embedders, retrievers, and evaluators.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    doc_id: str                          # Stable ID for the parent document
    source_path: str                     # Absolute path to the source file
    doc_type: DocumentType
    chunk_type: ChunkType
    content: str                         # Plain text representation (always present)
    page_number: int | None = None
    section_path: str | None = None      # e.g. "2.3 > Risk Factors > Market Risk"
    bounding_box: BoundingBox | None = None
    image_path: str | None = None        # Path to cropped image (figures/tables)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Set by contextual enrichment (retrieval pipeline)
    context_prefix: str | None = None   # Prepended doc/section summary

    @property
    def enriched_content(self) -> str:
        """Content with contextual prefix, used for embedding."""
        if self.context_prefix:
            return f"{self.context_prefix}\n\n{self.content}"
        return self.content


# ---------------------------------------------------------------------------
# Embedding result
# ---------------------------------------------------------------------------

class EmbeddedChunk(BaseModel):
    chunk: DocumentChunk
    vector: list[float]
    model_name: str


# ---------------------------------------------------------------------------
# Retrieval models
# ---------------------------------------------------------------------------

class RetrievedContext(BaseModel):
    """A chunk returned by the retriever, with its relevance score."""
    chunk: DocumentChunk
    score: float
    strategy: RetrievalStrategy
    rank: int


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    filters: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None


# ---------------------------------------------------------------------------
# Generation / answer models
# ---------------------------------------------------------------------------

class Citation(BaseModel):
    doc_id: str
    source_path: str
    page_number: int | None
    chunk_id: str
    excerpt: str


class QueryResponse(BaseModel):
    query: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    retrieved_contexts: list[RetrievedContext] = Field(default_factory=list)
    model_used: str | None = None
    latency_ms: float | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Evaluation models
# ---------------------------------------------------------------------------

class EvalSample(BaseModel):
    """A single question-answer pair for evaluation."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    question: str
    ground_truth_answer: str
    ground_truth_doc_ids: list[str] = Field(default_factory=list)
    doc_path: str | None = None          # e.g. data/raw/sample_report.pdf
    expected_pages: list[int] = Field(default_factory=list)
    page_tolerance: int = 3
    top_k: int = 5
    chunk_type_focus: ChunkType | None = None  # e.g. FIGURE for visual QA samples
    tags: list[str] = Field(default_factory=list)
    expect_conformity_flagged: bool | None = None  # taxonomy conformity eval


class MetricScore(BaseModel):
    name: str
    value: float
    details: dict[str, Any] = Field(default_factory=dict)


class EvalResult(BaseModel):
    """Result of evaluating one (query, response) pair."""
    sample_id: str
    query: str
    generated_answer: str
    ground_truth_answer: str
    retrieved_chunk_ids: list[str]
    metrics: list[MetricScore]
    passed: bool
    latency_ms: float | None = None
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


class EvalRunReport(BaseModel):
    """Aggregate report for a full evaluation run."""
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    system_label: str
    git_commit: str | None = None
    num_samples: int
    aggregate_metrics: dict[str, float]  # metric_name -> mean score
    sample_results: list[EvalResult]
    run_at: datetime = Field(default_factory=datetime.utcnow)
    regression_alerts: list[str] = Field(default_factory=list)
