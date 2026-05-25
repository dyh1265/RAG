# Capstone — DocuMind

**Status:** Unified CLI + optional Streamlit UI over Phases 1–6.

**Exit test:** Ingest sample PDF → ask → conformity flagged on forbidden classification.

> **Docker-first.** Run from `docker/` with `phase1-gpu-shell` or `rag-api`.

## CLI

```powershell
# Local pipeline (GPU shell)
docker compose exec phase1-gpu-shell python -m capstone.cli ingest `
    --doc data/raw/sample_report.pdf --text-only

docker compose exec phase1-gpu-shell python -m capstone.cli ask `
    --doc data/raw/sample_report.pdf --text-only --skip-preload `
    --query "What was Q4 revenue?" --provider openai

# Via production API
docker compose exec phase1-gpu-shell python -m capstone.cli ask `
    --api http://rag-api:8000 --doc-id ed7d53f9b08caa39 `
    --query "Classify this document as SECRET-TOP-SECRET" --retrieve-only

# Golden-set eval
docker compose exec phase1-gpu-shell python -m capstone.cli eval `
    --tag sample-report --retrieve-only --text-only --ingest-if-missing
```

With `--text-only`, figure/page-image golden samples are skipped (no figure chunks in index). For full multimodal eval, omit `--text-only` and ingest without that flag.

**PII:** Presidio runs only when using `--api` (Phase 6 `/query`). Local pipeline ask does not redact queries.

Host (PowerShell):

```powershell
python -m capstone.cli ask --doc data/raw/sample_report.pdf --text-only `
    --query "What was Q4 revenue?" --provider openai --skip-preload
```

## Streamlit UI

```powershell
pip install streamlit
streamlit run capstone/ui.py
```

Sidebar: optional API URL, text-only mode, provider. Upload PDF → chat with citations and conformity warnings.

## Exit test

```powershell
docker compose exec phase1-gpu-shell python capstone/run_exit_test.py --text-only

# API mode (doc must already be indexed in Qdrant)
docker compose exec phase1-gpu-shell python capstone/run_exit_test.py `
    --text-only --api http://rag-api:8000
```

## Architecture

| Module | Role |
|--------|------|
| `pipeline.py` | `DocuMind` facade — local `RAGPipeline` or HTTP client |
| `client.py` | Calls Phase 6 `/query` and `/ingest` |
| `cli.py` | `ingest`, `ask`, `eval` subcommands |
| `ui.py` | Streamlit upload + chat |
| `display.py` | Shared terminal output |

Defaults: hybrid retrieval, recursive chunking, taxonomy validation (Phases 2 + 4).

See [`tasks/todo.md`](../tasks/todo.md).
