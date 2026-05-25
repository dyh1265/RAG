# Pre-existing test fixes

- [x] `test_generate_openai_calls_api_and_builds_citations`: lengthen fixture content past `is_substantive_content` 40-char threshold
- [x] `test_generate_openai_requires_api_key`: same fixture-content fix so the OpenAI path is reached
- [x] `test_ingest_parses_embeds_and_upserts`: build pipeline with all enrichment flags off (avoids `apply_section_paths` opening the mocked PDF path)
- [x] `test_query_generates_answer`: disable `use_taxonomy_validation` so `apply_conformity_check`'s `model_copy` doesn't replace the mocked response
- [x] `test_doc_fingerprint_changes_on_write`: real bug — fingerprint now incorporates a 64 KB content sample, robust to NTFS sub-tick mtime collisions
- [x] Full unit suite: **88 passed, 0 failed**

---

# Phase architecture removal

- [x] Rename `Phase2IngestConfig` → `RetrievalIngestConfig`, `apply_phase2_ingest` → `apply_retrieval_ingest`, `invalidate_phase2_caches` → `invalidate_retrieval_caches`
- [x] Rename `RAGPipeline._phase2_enabled` → `_retrieval_enrichment_enabled`
- [x] Strip `Phase N` from all docstrings, comments, package `__init__` files
- [x] Update CONTRIBUTING.md (drop `[phase1,phase2]` extras, replace phase-scoped test paths with module-scoped)
- [x] Update PR template (`Phase / area` → `Module / area`)
- [x] Update `.env.example`, `scripts/generate_*.py`, frontend Sidebar footer, FastAPI title
- [x] Verify: zero `phase` references in repo (`rg -i phase` returns 0)
- [x] Pytest: 84 passed / 4 pre-existing failures (Windows path, env leakage, mock issues — not from rename)
- [x] Ruff: clean
- [x] API rebuilt; `/api/health` 200; OpenAPI title is `DocuMind API`

---

# Compose unification (Cloudflare-style)

- [x] Drop `nginx` service; use `documind-web` nginx for SPA + `/api`
- [x] Bind qdrant/redis/rag-api to `127.0.0.1`
- [x] `documind-web` listens on `:80` directly
- [x] Move `documind-web-dev` to `dev` profile, add `rag-api` to dev
- [x] Delete `docker/docker-compose.demo.yml`
- [x] Update `bootstrap-oracle.sh`, root README, `deploy/README.md`
- [x] Verify: `http://localhost/` (200), `http://localhost/api/health` ({"status":"ok"})

---

# RAG evaluation scaffold

## Plan
- [x] Explore pipeline, chunk metadata, sample PDFs
- [x] Add `tests/eval/golden_set.jsonl` with labelled Q&A
- [x] Add retrieval metrics (`Recall@k`, MRR) + `test_retrieval.py`
- [x] Add Ragas answer-quality tests + optional dev deps
- [x] Wire `config.py` thresholds into eval helpers
- [x] Add CI/nightly workflow (optional, mark integration)
- [x] Run pytest on eval (unit parts) and document in README snippet

## Review
- **Verification:** `pytest tests/eval/test_metrics.py -v` (7 passed); `ruff check tests/eval`.
- **Behavior:** Golden set over `sample_report.pdf` (`doc_id=ed7d53f9b08caa39`); retrieval thresholds from settings; keyword coverage + optional Ragas when `RUN_RAGAS_EVAL=1`.
- **Residual risks:** Integration eval needs local Qdrant + embedding download; thresholds may need tuning on first CI run; Ragas job skipped without `OPENAI_API_KEY` secret.

---

# Repo audit (round 2)

## Findings (subagent + manual sweep)

- [x] `data/raw/sample_report.pdf` regenerated; quickstart + eval golden set are no longer broken
- [x] `frontend/README.md` rewritten — `production` profile on :80, `dev` profile on :5173 (was wrong: `--profile production documind-web-dev`, `:5174`)
- [x] `frontend/src/api/client.ts`: drop dead `:5174` port branch, use `window.location.port !== "8002"` instead
- [x] `docker/docker-compose.yml`: mount `huggingface_cache` → `/root/.cache/huggingface` on `rag-api` + `ingest-worker` (volume was declared but never attached)
- [x] `docker/docker-compose.yml`: bind-mount `../scripts:/app/scripts` so `docker compose exec ingest-worker python scripts/...` works
- [x] `docker/docker-compose.yml`: `DOCUMIND_WEB_PORT` env var actually drives the port mapping (was a doc lie)
- [x] `docker/prometheus/prometheus.yml`: `host.docker.internal:8000` → `rag-api:8000` (was unreachable on Linux hosts)
- [x] `docker/nginx/nginx.conf` deleted (orphan from removed standalone nginx service)
- [x] `backend/ingestion/retrieval/reranker.py`: docstring `shared/config.py` → `backend/core/config.py`
- [x] `tests/test_models.py`: docstring `shared/models.py` → `backend/core/models.py`
- [x] `.env.example`: dropped phase wording, added `OTLP_ENDPOINT`, `TAXONOMY_BLOCK_FORBIDDEN`, `USE_PII_REDACTION_ON_INGEST` blocks; pointed at `backend/core/config.py`
- [x] `deploy/.env.demo.example`: cleaned the "Phase 2 + 4" comment
- [x] `deploy/bootstrap-oracle.sh`: include `ingest-worker` in initial up so bulk ingest works on first boot
- [x] `deploy/README.md`: `YOUR_USER/RAG` → `dyh1265/RAG`; `DOCUMIND_WEB_PORT` doc matches reality
- [x] `README.md` + `pyproject.toml`: GitHub URLs `dyh/advanced-rag` → `dyh1265/RAG`
- [x] `README.md` Backend dev section: `cd docker/` parens around `docker compose up -d qdrant ...`; sample-data section drops nonexistent `long_report.pdf` regen claim
- [x] `.github/workflows/eval.yml`: pin Qdrant `v1.12.5` (matches compose); generate sample PDF before eval

## Verification
- `ruff check .` → all checks pass
- `pytest tests/ -m "not integration and not eval" -q` → 88 passed
- `docker compose --profile production --profile dev config --quiet` → exit 0
- `curl http://localhost/` → 200; `/api/health` → `{"status":"ok"}`; `:6333/healthz` → 200

## Residual / known issues
- **Live `OPENAI_API_KEY` in user's `.env`** (never committed; gitignored). It was disclosed in this chat, so rotate at platform.openai.com → Settings → API keys before any sharing.
- `huggingface_cache` only takes effect on next `docker compose up -d --build rag-api ingest-worker` (or `down` + up); existing containers keep their original layer.
- `pyproject.toml` declares some deps (`owlready2`, `networkx`, `aiofiles`, `surya-ocr`, `langchain-qdrant`, `python-docx`, `structlog`, `rich`, `tqdm`) that ripgrep can't find imports for — left untouched; some are loaded transitively or via plugins (`rdflib` ↔ `owlready2`, etc.). Trim later under a deps-cleanup task with a fresh `pip install -e .` run.

---

# Layout refactor — collapse `retrieval/retrieval/`, lift query-time code

## Plan
- Flatten `backend/retrieval/retrieval/` into `backend/retrieval/`
- Move query-time files out of `backend/ingestion/retrieval/` into `backend/retrieval/`
- Promote `backend/ingestion/generation/` to top-level `backend/generation/`
- Rename `backend/retrieval/ingest.py` → `preprocessing.py` (the file ran at ingest time but lived under retrieval — rename disambiguates)
- Rename `reranker.py` → `cross_encoder_reranker.py` for symmetry with `flashrank_reranker.py`
- Mirror in `tests/`: move `test_answer_generator.py` → `tests/generation/`; `test_chunk_filters.py` and `test_multimodal_retriever.py` → `tests/retrieval/`
- Extract shared helpers (`make_chunk`, `make_context`) from `tests/ingestion/conftest.py` into `tests/_factories.py` so cross-package test imports stop reaching into ingestion's conftest

## Result — top-level packages, single concern each
```
backend/
├── core/         config, models, RAGPipeline
├── ingestion/    parsers + embeddings + stores + ingestion_pipeline
├── retrieval/    chunking + enrichment + hybrid + parent_expand + multimodal +
│                 cross_encoder_reranker + flashrank_reranker + chunk_filters +
│                 preprocessing
├── generation/   answer_generator
├── api/, scaling/, taxonomy/   (unchanged)
```

## Verification
- `ruff check .` → clean
- `pytest tests/ -m "not integration and not eval" -q` → **88 passed**
- `rg "(backend\.ingestion\.retrieval|backend\.ingestion\.generation|backend\.retrieval\.retrieval|tests\.ingestion\.conftest)"` → 0 matches
- Live: `docker compose restart rag-api ingest-worker` clean startup; `/api/health` 200, `/api/ready` 200, `/api/admin/documents` 200 with real ingested docs (proves the full import chain — pipeline → multimodal_retriever → hybrid → cross_encoder → preprocessing → flashrank → answer_generator — resolves under the new layout)

## Residual
- `backend/__init__.py` and most subpackage `__init__.py` files are empty; relying on namespace packages. Still works; left as-is.
- The `(cd docker && ...)` parens in the README `Backend dev` block are bash; Windows users in PowerShell need `Push-Location/Pop-Location`. Same shape as before this refactor — not regressed.
