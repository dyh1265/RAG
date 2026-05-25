# Phase 3 — Scalable ingestion

**Status:** Celery worker, Redis embedding cache, MinHash dedup, skip unchanged docs, Prometheus metrics.

**Exit test:** 100+ PDFs ingested; second pass skips unchanged; metrics on `:9100/metrics`.

> **Run commands below are Docker-first.** Start from the `docker/` directory.

## Start infrastructure

```powershell
cd docker
docker compose up -d qdrant redis prometheus grafana
docker compose --profile phase3 up -d ingest-worker
```

| Service | URL |
|---------|-----|
| Redis | `localhost:6379` |
| Ingest metrics | http://localhost:9100/metrics |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin) |

## Generate 100 test PDFs

```powershell
cd docker
docker compose exec ingest-worker python scripts/generate_bulk_pdfs.py --count 100
# PDFs land in data/raw/bulk/ (host-mounted)
```

## Bulk ingest (100 PDFs)

**Sync inside ingest-worker** (no Celery, good for testing):

```powershell
cd docker
docker compose --profile phase3 up -d qdrant redis ingest-worker
docker compose exec ingest-worker python phases/phase_03_scalable_ingestion/bulk_ingest.py `
    --glob "data/raw/bulk/*.pdf" --sync --text-only --hybrid --recursive-chunk
```

**Async via Celery** (queue from host or worker container):

```powershell
cd docker
docker compose exec ingest-worker python phases/phase_03_scalable_ingestion/bulk_ingest.py `
    --glob "data/raw/bulk/*.pdf" --text-only --hybrid --recursive-chunk
docker compose logs -f ingest-worker
```

**GPU warm shell** (alternative sync path — install phase3 deps once):

```powershell
cd docker
docker compose --profile phase1-gpu up -d qdrant redis phase1-gpu-shell --force-recreate
docker compose exec phase1-gpu-shell pip install redis datasketch prometheus-client celery
docker compose exec phase1-gpu-shell python phases/phase_03_scalable_ingestion/bulk_ingest.py `
    --glob "data/raw/bulk/*.pdf" --sync --text-only --hybrid --recursive-chunk
```

## Exit test

```powershell
cd docker
docker compose --profile phase3 up -d qdrant redis ingest-worker
docker compose exec ingest-worker python phases/phase_03_scalable_ingestion/run_exit_test.py --count 100 --text-only
```

Or with the pre-generated bulk set:

```powershell
docker compose exec ingest-worker python scripts/generate_bulk_pdfs.py --count 100
docker compose exec ingest-worker python phases/phase_03_scalable_ingestion/bulk_ingest.py `
    --glob "data/raw/bulk/*.pdf" --sync --text-only
# Re-run same command — expect all skipped (unchanged)
```

## Features

| Feature | Module |
|---------|--------|
| Celery `ingest_document` task | `workers/tasks.py` |
| Redis embedding cache | `embedding/redis_cache.py` |
| Skip unchanged docs (fingerprint) | `embedding/fingerprint.py` |
| MinHash dedup | `embedding/dedup.py` |
| Text-only ingest mode | `pipeline/ingest_modes.py` |
| Prometheus metrics | `monitoring/metrics.py` |

## CLI flags (`bulk_ingest.py`)

| Flag | Purpose |
|------|---------|
| `--glob` | PDF glob pattern (required in Docker on Windows) |
| `--sync` | Run inline without Celery |
| `--text-only` | Skip figure/page parsers |
| `--force` | Re-ingest even when fingerprint unchanged |
| `--no-cache` | Disable Redis embedding cache |
| `--no-dedup` | Disable MinHash near-duplicate removal |
| `--clear-done` | Reset Celery resume set in Redis |

## Host install (optional)

```bash
pip install -e ".[phase1,phase2,phase3]"
```

See [`tasks/todo.md`](../tasks/todo.md).
