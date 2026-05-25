# Lessons learned

## Documentation

- **Always give Docker commands first** when documenting run/test workflows. Assume the user runs from `docker/` with `docker compose exec` on `phase1-gpu-shell` or `ingest-worker`. Include host/local commands only as a secondary option.

## Phase 3 / Celery

- Celery prefork workers must not each call `start_http_server()` on the same port — use `worker_ready` + `PROMETHEUS_MULTIPROC_DIR`, never start metrics inside task handlers.

## Docker

- Recreate containers after adding volume mounts: `docker compose --profile phase1-gpu up -d qdrant redis phase1-gpu-shell --force-recreate`
- Use `--glob "data/raw/bulk/*.pdf"` in bulk_ingest inside containers (shell glob may not expand on Windows exec).
