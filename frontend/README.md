# DocuMind Web — React + Vite frontend

React + Vite SPA for the DocuMind backend API. Upload PDFs, chat with citations, see taxonomy conformity warnings.

> **Docker-first.** Run npm commands from `docker/` if you don't want a local Node install.

## Quick start (production demo, Cloudflare-style)

```powershell
cd docker
docker compose --profile production up -d --build
```

Open **http://localhost** — the `documind-web` container serves the bundle on port 80 and proxies `/api/*` to `rag-api` inside the compose network.

## Frontend hot reload (dev)

```powershell
cd docker
docker compose --profile dev up -d --build
```

Open **http://localhost:5173** — Vite proxies `/api` → `rag-api:8000` inside the compose network.

## npm via Docker

One-off commands (install, build, test) — uses the `dev` profile container:

```powershell
cd docker

# Install / refresh dependencies (writes to documind_node_modules volume)
docker compose --profile dev run --rm documind-web-dev npm install

# Production build (output in frontend/dist on host via bind mount)
docker compose --profile dev run --rm documind-web-dev npm run build

# Interactive shell
docker compose --profile dev run --rm documind-web-dev sh
```

## Local Node toolchain

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api -> http://localhost:8002
npm run build    # outputs dist/
```

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_RAG_API_URL` | `/api` (compose builds), `http://localhost:8002` (Dockerfile fallback) | Backend API base URL in browser |
| `VITE_DEV_API_PROXY` | `http://rag-api:8000` | Vite dev proxy target inside compose |
| `VITE_DEMO_UI` | `true` (compose default) | Hide developer-only UI (API URL field, debug footer) |
| `DOCKER` | `true` in compose | Fallback proxy to `rag-api:8000` |

The sidebar API URL (developer mode only) is persisted in `localStorage`.

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
