# DocuMind

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/dyh/advanced-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/dyh/advanced-rag/actions/workflows/ci.yml)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker)](docker/docker-compose.yml)

Upload a PDF, chat with it, get cited answers. Production-grade multimodal RAG over text, tables, and figures — with hybrid retrieval, taxonomy conformity checks, PII redaction, and an OpenTelemetry-instrumented FastAPI backend.

## Architecture

```mermaid
flowchart LR
    Browser[Browser] --> FE[frontend<br/>React + Vite]
    FE -->|"HTTP /api/*"| API[backend.api<br/>FastAPI]
    API --> Pipeline[backend.core<br/>RAGPipeline]
    Pipeline --> Ingest[backend.ingestion]
    Pipeline --> Ret[backend.retrieval]
    Pipeline --> Tax[backend.taxonomy]
    API -->|"POST /ingest/bulk/*"| Worker[Celery worker<br/>backend.scaling.workers]
    Ingest --> Qdrant[(Qdrant)]
    Worker --> Qdrant
    Worker --> Redis[(Redis)]
    Pipeline -.OpenTelemetry.-> Jaeger[(Jaeger)]
    API -.Prometheus.-> Grafana[(Grafana)]
```

## Layout

| Path | What |
|---|---|
| [`backend/`](backend/) | Python package — single import root |
| `backend/api/` | FastAPI app (`backend.api.main:app`), routers, schemas, guardrails, monitoring, load tests |
| `backend/core/` | Shared config, models, RAG pipeline orchestrator |
| `backend/ingestion/` | PDF parsing, OCR, embeddings, Qdrant store, generation |
| `backend/retrieval/` | Hybrid retrieval, chunking, enrichment, parent-expand, FlashRank reranker |
| `backend/scaling/` | Celery bulk-ingest workers, Redis cache, dedup, fingerprinting |
| `backend/taxonomy/` | RDF taxonomy validation, conformity hooks, fuzzy entity linking |
| [`frontend/`](frontend/) | React + Vite UI (chat, citations, document admin, bulk upload) |
| [`docker/`](docker/) | Compose stack: Qdrant, Redis, Prometheus, Grafana, Jaeger, API, worker, web |
| [`tests/`](tests/) | Pytest suite mirroring `backend/` layout |
| [`data/`](data/) | `raw/` (PDFs, gitignored except samples), `processed/` (cache), `taxonomies/` (RDF) |
| [`deploy/`](deploy/) | Public-demo guides for Oracle/Fly/Cloudflare/GCP |
| [`scripts/`](scripts/) | Synthetic PDF generators for the demo |

## Quickstart

### 1. Set the API key

```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY=sk-...
```

### 2. Start everything in Docker

```bash
cd docker
docker compose --profile production up -d --build
```

First build downloads PyTorch + spaCy + Presidio (~3 GB). On a 4 GB+ VM, expect 10–15 min.

| Service | URL |
|---|---|
| Frontend (prod nginx) | http://localhost:5174 |
| Frontend (dev hot-reload) | http://localhost:5173 |
| Backend API | http://localhost:8002/health |
| Qdrant dashboard | http://localhost:6333/dashboard |
| Grafana | http://localhost:3000 (admin/admin) |
| Prometheus | http://localhost:9090 |
| Jaeger tracing | http://localhost:16686 |

### 3. Use it

Open http://localhost:5174 → upload [`data/raw/sample_report.pdf`](data/raw/sample_report.pdf) → ask "What does Figure 3 show about revenue trends?".

## Backend dev

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1            # Windows; macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"

# Run the API locally (needs Qdrant + Redis from docker compose)
docker compose up -d qdrant redis
uvicorn backend.api.main:app --reload --port 8002

# Run the Celery worker
celery -A backend.scaling.workers.celery_app worker --loglevel=info --concurrency=1

# Tests + lint
pytest tests/ -m "not integration" -v
ruff check .

# RAG quality eval (needs Qdrant; answer tests need OPENAI_API_KEY)
docker compose up -d qdrant   # from docker/
pytest tests/eval/test_metrics.py -v
pytest tests/eval/ -m eval -v
```

## Frontend dev

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api/* to http://localhost:8002
```

Build for production:

```bash
npm run build   # outputs dist/
```

## Configuration

All backend settings live in [`backend/core/config.py`](backend/core/config.py) and can be overridden in `.env`. Common toggles:

| Env var | Default | What it does |
|---|---|---|
| `OPENAI_API_KEY` | _required_ | OpenAI generation + embeddings |
| `USE_HYBRID` | `true` | BM25 + dense retrieval fusion |
| `USE_RECURSIVE_CHUNKER` | `true` | Token-aware splitter |
| `USE_COLPALI` | `false` | Page-image embeddings (needs GPU) |
| `USE_TAXONOMY_VALIDATION` | `true` | Block answers that violate the RDF taxonomy in `data/taxonomies/` |
| `USE_PII_REDACTION` | `true` | Presidio + spaCy redaction on query and ingest |
| `USE_OCR` | `true` | Tesseract OCR for image-only PDF pages |
| `API_WARMUP_MODELS` | `true` | Eager model load on boot (slower start, faster first query) |

## Sample data

[`data/raw/sample_report.pdf`](data/raw/sample_report.pdf) and [`data/raw/long_report.pdf`](data/raw/long_report.pdf) are tracked for the quickstart. Everything else under `data/raw/` and all of `data/processed/` is gitignored. Regenerate via [`scripts/generate_sample_report.py`](scripts/generate_sample_report.py) and [`scripts/generate_bulk_pdfs.py`](scripts/generate_bulk_pdfs.py).

## Public demo

See [`deploy/README.md`](deploy/README.md) for Oracle/Fly/Cloudflare/GCP options. Bare minimum: a 4 GB VM + the same Docker stack.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security issues: [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE).
