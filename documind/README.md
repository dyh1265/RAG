# DocuMind — Unified Package

One import path for the whole RAG system. Phase implementations live under `phases/`; **import from `documind` for new code**.

## Layout

| Package | Source | Purpose |
|---------|--------|---------|
| `documind.core` | `shared/` | Config, models, `RAGPipeline` |
| `documind.ingestion` | `phases/phase_01_multimodal_ingestion/` | Parse PDFs, embed, Qdrant |
| `documind.retrieval` | `phases/phase_02_long_doc_retrieval/` | Hybrid search, FlashRank |
| `documind.scaling` | `phases/phase_03_scalable_ingestion/` | Bulk ingest modes, Celery |
| `documind.taxonomy` | `phases/phase_04_taxonomy_generation/` | Conformity validation |
| `documind.evaluation` | `phases/phase_05_evaluation/` | Golden-set eval (CLI scripts) |
| `documind.production` | `phases/phase_06_production/` | FastAPI app, PII guardrails |
| `documind.cli` | `capstone/` | CLI and API client |

## Quick usage

```python
from documind import RAGPipeline, DocuMind, get_settings
from documind.ingestion import QdrantStore, PDFTextParser
from documind.production import app  # FastAPI ASGI app

pipeline = RAGPipeline()
pipeline.ingest("data/raw/report.pdf")
response = pipeline.query(...)  # QueryRequest
```

```bash
# CLI (unchanged entry point)
documind ingest --doc data/raw/report.pdf
python -m capstone.cli ask --doc-id ... --query "..."

# API
uvicorn phases.phase_06_production.api.main:app
# or
uvicorn documind.production:app
```

## Migration

Preferred and legacy imports:

```python
from documind import RAGPipeline                         # preferred
from phases.phase_01_multimodal_ingestion.stores.qdrant_store import QdrantStore
from phase_01_multimodal_ingestion.stores.qdrant_store import QdrantStore  # legacy shim
from shared.pipeline import RAGPipeline                  # still OK
```

Legacy bare `phase_*` imports are redirected to `phases.phase_*` via `phases._legacy`.
