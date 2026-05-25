# DocuMind Web — Node.js frontend

React + Vite SPA for the DocuMind backend API. Upload PDFs, chat with citations, and see taxonomy conformity warnings.

> **Docker-first.** Run all npm commands from `docker/` — no local Node install required.

## Quick start (dev with hot reload)

```powershell
cd docker
docker compose --profile production up -d qdrant redis rag-api documind-web-dev
```

Open http://localhost:5173 — Vite proxies `/api` → `rag-api:8000` inside the compose network.

## npm via Docker

One-off commands (install, build, test):

```powershell
cd docker

# Install / refresh dependencies (writes to documind_node_modules volume)
docker compose --profile production run --rm documind-web-dev npm install

# Production build (output in frontend/dist on host via bind mount)
docker compose --profile production run --rm documind-web-dev npm run build

# Interactive shell
docker compose --profile production run --rm documind-web-dev sh
```

## Production static build (nginx)

```powershell
cd docker
docker compose --profile production build documind-web
docker compose --profile production up -d qdrant redis rag-api documind-web
```

UI: http://localhost:5174 (nginx serving the built bundle)

Build arg `VITE_RAG_API_URL` sets the API URL baked into the bundle (default `http://localhost:8002` for browser → host port 8002).

## Configuration

| Variable | Default (Docker dev) | Purpose |
|----------|----------------------|---------|
| `VITE_RAG_API_URL` | `/api` in dev | Backend API base URL in browser |
| `VITE_DEV_API_PROXY` | `http://rag-api:8000` | Vite dev proxy target inside compose |
| `DOCKER` | `true` in compose | Fallback proxy to `rag-api:8000` |

The sidebar API URL is persisted in `localStorage`. Leave default `/api` in dev mode.

## Features

- PDF upload → `POST /ingest`
- Chat scoped to `doc_id` → `POST /query`
- Citation expander (page + excerpt)
- Conformity warning banner (taxonomy)
- PII redaction notice when `pii_redacted` is true
- Provider toggle: OpenAI / Ollama
- Health / ready status badge
- **Recent documents** sidebar — switch between indexed PDFs, persisted in `localStorage` + synced from `GET /admin/documents`

## Stack

- Node 22 (Alpine), Vite 6, React 19, TypeScript
- No UI framework — custom CSS
