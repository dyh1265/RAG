# Phase 6 — Production API

**Status:** FastAPI service with query/ingest/admin routes, PII redaction, rate limiting, Prometheus metrics, OpenTelemetry tracing.

**Exit test:** `docker compose --profile production up` → health/ready/metrics → conformity on forbidden query → PII redacted.

> **Docker-first.** Run from `docker/`.

## Start stack

```powershell
cd docker
docker compose --profile production build rag-api
docker compose --profile production up -d qdrant redis jaeger rag-api

# Optional reverse proxy + nginx rate limit
docker compose --profile production up -d nginx
```

API: http://localhost:8002 (host port; container listens on 8000)  
Jaeger UI: http://localhost:16686

## Query (JSON)

```powershell
curl.exe -X POST http://localhost:8002/query `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"Classify this document as SECRET-TOP-SECRET\",\"doc_id\":\"ed7d53f9b08caa39\",\"retrieve_only\":true,\"provider\":\"openai\"}"
```

Response includes `metadata.conformity` (Phase 4) and `pii_redacted` when Presidio modifies the query.

**PII policy:** Redaction runs on **queries**, **answers**, **citation excerpts**, and **retrieved context** in `/query` responses. When `USE_PII_REDACTION_ON_INGEST=true` (default), chunk text is redacted before indexing. Fiscal quarters like `Q4` are preserved. Set `USE_PII_REDACTION=false` to disable. Re-ingest documents after enabling ingest redaction. Local `capstone.cli ask` without `--api` does not run Presidio on responses.

On startup, `API_WARMUP_MODELS=true` (default) preloads embedding/reranker models in the background so the first `/query` is faster.

## Query (SSE stream)

```powershell
curl.exe -N -X POST http://localhost:8002/query/stream `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"What was Q4 revenue?\",\"doc_id\":\"ed7d53f9b08caa39\",\"retrieve_only\":true}"
```

## Ingest upload

```powershell
curl.exe -X POST http://localhost:8002/ingest `
  -F "file=@../data/raw/sample_report.pdf"
```

## Ingest directory (all PDFs)

```powershell
curl.exe -X POST http://localhost:8002/ingest/directory `
  -H "Content-Type: application/json" `
  -d "{\"directory\":\"data/raw/applications\",\"recursive\":true}"
```

Path must be under `data/raw`. Returns per-file ingest stats.

**CLI (DocuMind):**

```powershell
docker compose exec phase1-gpu-shell python -m capstone.cli ingest-dir `
  --dir data/raw/applications --text-only --hybrid --skip-preload
```

**Phase 3 bulk (Celery / cache / dedup):**

```powershell
docker compose exec ingest-worker python phases/phase_03_scalable_ingestion/bulk_ingest.py `
  --dir data/raw/applications --sync --text-only --hybrid --recursive-chunk
```

## Admin

```powershell
curl.exe http://localhost:8002/admin/collections
curl.exe -X DELETE http://localhost:8002/admin/doc/ed7d53f9b08caa39
```

## Exit test

```powershell
docker compose exec rag-api python phases/phase_06_production/run_exit_test.py
```

## Load test (Locust)

```powershell
docker compose exec rag-api locust -f phases/phase_06_production/load/locustfile.py --headless -u 5 -r 1 -t 30s --host http://localhost:8002
```

Compare p95 latency to `eval_latency_p95_ms` in config (default 3000ms).

## Architecture

| Module | Role |
|--------|------|
| `api/main.py` | FastAPI app, lifespan → `RAGPipeline` |
| `api/routers/query.py` | `/query`, `/query/stream` |
| `api/routers/ingest.py` | PDF upload → `pipeline.ingest()` |
| `api/routers/admin.py` | Collection stats, delete doc |
| `guardrails/pii.py` | Presidio redaction on queries |
| `monitoring/metrics.py` | Prometheus `/metrics` |
| `monitoring/tracing.py` | OTLP → Jaeger |

See [`tasks/todo.md`](../tasks/todo.md).
