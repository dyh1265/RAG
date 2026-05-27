# Configuration

Every backend setting comes from [`backend/core/config.py`](https://github.com/dyh1265/RAG/blob/master/backend/core/config.py) — a single `pydantic-settings` `Settings` class. There are no scattered `os.getenv()` calls. Override anything via `.env` (gitignored) or real environment variables; aliases below are what you put in the env.

If you only need the common toggles, the [README's Configuration table](https://github.com/dyh1265/RAG#configuration) is the short version. This page is the full reference.

## LLM provider

| Env var | Default | What |
|---|---|---|
| `OPENAI_API_KEY` | *required for OpenAI mode* | Set this to use OpenAI for generation and embeddings. |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI chat model. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama. In Docker: `http://host.docker.internal:11434`. |
| `HF_TOKEN` | unset | Optional Hugging Face token for faster / gated model downloads. |

## Embeddings & retrieval models

| Env var | Default | What |
|---|---|---|
| `TEXT_EMBEDDING_MODEL` | `BAAI/bge-m3` | Multilingual text encoder. |
| *(code-only)* `image_embedding_model` | `laion/CLIP-ViT-B-32-laion2B-s34B-b79K` | CLIP for figure / table image chunks. |
| `COLPALI_MODEL` | `vidore/colqwen2-v1.0` | ColPali model. Use `vidore/colSmol-500M` on CPU. |
| `USE_COLPALI` | `false` | Enable page-image retrieval. Requires GPU for tolerable latency. |
| *(code-only)* `reranker_model` | `BAAI/bge-reranker-v2-m3` | Cross-encoder used when `use_rerank=True` is passed to the pipeline. |
| `EMBEDDING_DEVICE` | `cpu` | Set to `cuda` if a GPU is present. |

## Retrieval pipeline toggles

All defaults are tuned for the in-tree sample report and the CI golden set. See [Retrieval](Retrieval) for what each flag changes.

| Env var | Default | What |
|---|---|---|
| `USE_HYBRID` | `false` | BM25 + dense fusion on `text_chunks`. Recommended `true` for production. |
| `USE_RECURSIVE_CHUNKER` | `false` | Token-aware splitter (recommended on; sample uses default). |
| `USE_SEMANTIC_CHUNKER` | `false` | Alternative to recursive — splits on semantic boundaries. |
| `SEMANTIC_CHUNK_THRESHOLD` | `0.75` | Cosine threshold for the semantic chunker. |
| `USE_SECTION_PATHS` | `true` | Carry the heading chain (`Section > Subsection`) on every chunk. |
| `USE_CONTEXT_ENRICHMENT` | `true` | Pre-compute neighbouring-sentence context windows at ingest. |
| `USE_PARENT_EXPAND` | `true` | On a child-chunk hit, expand to the parent passage. |
| `USE_FLASHRANK` | `false` | Lightweight cross-encoder rerank, ~25 ms / 10 chunks. |

## Vector DB (Qdrant)

| Env var | Default | What |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | Qdrant base URL. |
| `QDRANT_API_KEY` | empty | Only needed for Qdrant Cloud. |
| *(code-only)* `qdrant_collection_text` / `_tables` / `_figures` / `_pages` | as named | Collection names per modality. |
| *(code-only)* `qdrant_upsert_batch_size` | `64` | Tune for memory-constrained workers. |

## Redis, cache, queue

| Env var | Default | What |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379` | Redis. |
| `CELERY_BROKER_URL` | falls back to `REDIS_URL` | Override only if broker ≠ cache. |
| *(code-only)* `embedding_cache_ttl_seconds` | 7 days | TTL on the Redis embed cache. |
| `INGEST_METRICS_PORT` | `9100` | Prometheus port the worker exposes. |
| `DEDUP_SIMILARITY_THRESHOLD` | `0.85` | LSH similarity above which two PDFs are treated as duplicates at bulk-ingest time. |

## OCR & PDF processing

| Env var | Default | What |
|---|---|---|
| `USE_OCR` | `true` | Tesseract OCR for image-only PDF pages at ingest. |
| `OCR_LANG` | `eng` | Tesseract language code. |
| *(code-only)* `max_chunk_size` | `512` tokens | Chunker target. |
| *(code-only)* `chunk_overlap` | `64` tokens | Chunker overlap. |
| *(code-only)* `max_workers` | `4` | Async ingestion workers. |

## API & guardrails

| Env var | Default | What |
|---|---|---|
| `API_RATE_LIMIT_PER_MINUTE` | `60` | Per-IP cap for `/query` and single-file `/ingest`. |
| `API_RATE_LIMIT_BULK_PER_MINUTE` | `2000` | Per-IP cap for bulk uploads and job-status polling. |
| `CORS_ALLOW_ORIGINS` | `*` | Comma-separated. Use `*` for demos; in production set explicit origins (e.g. `https://docu.example.com`). When explicit, the middleware also enables `allow_credentials`. |
| `USE_PII_REDACTION` | `true` | Presidio + spaCy redaction on `/query` text. |
| `USE_PII_REDACTION_ON_INGEST` | `true` | Same redaction at ingest. |
| `USE_TAXONOMY_VALIDATION` | `true` | Run the RDF taxonomy guard on generated answers. |
| `TAXONOMY_BLOCK_FORBIDDEN` | `false` | `true` hard-blocks forbidden mentions; `false` only warns and annotates. |
| `API_WARMUP_MODELS` | `true` | Eager-load text / image / reranker models on boot (slower start, faster first query). |

## Observability

| Env var | Default | What |
|---|---|---|
| `OTLP_ENDPOINT` | `http://localhost:4317` | OpenTelemetry collector. In docker compose: `http://jaeger:4317`. |
| `LOG_LEVEL` | `INFO` | Structlog level. |
| *(code-only)* `prometheus_port` | `9090` | Reserved for future Prom scrape config. |

## Evaluation thresholds

These are the same numbers the [Evaluation](Evaluation) page lists, exposed as env vars so a slow CI runner can raise the latency budget without rewriting the test.

| Env var | Default | What |
|---|---|---|
| `EVAL_TOP_K` | `10` | `top_k` used during the retrieval eval (the metrics still cut at K=5). |
| `EVAL_RECALL_AT_5_THRESHOLD` | `0.70` | CI floor for recall@5. |
| `EVAL_HIT_AT_5_THRESHOLD` | `0.80` | CI floor for hit@5. |
| `EVAL_MRR_THRESHOLD` | `0.50` | CI floor for MRR. |
| `EVAL_KEYWORD_COVERAGE_THRESHOLD` | `0.66` | CI floor for answer keyword coverage. |
| `EVAL_RETRIEVAL_LATENCY_P95_MS` | `60000` | CI ceiling for retrieve-only p95 wall clock after warmup. |
| `EVAL_LATENCY_P95_MS` | `60000` | Reserved for future end-to-end p95 checks. |
| *(code-only)* `eval_faithfulness_threshold` | `0.85` | Ragas faithfulness floor (opt-in). |
| `RUN_RAGAS_EVAL` | unset | Set to `1` after `pip install -e ".[eval]"` to run the Ragas-based faithfulness test. |

## Reproducible builds

| Env var | Default | What |
|---|---|---|
| `SOURCE_DATE_EPOCH` | `1704067200` (2024-01-01 UTC) | Pinning every wall-clock leak (PDF `/CreationDate`, PNG `Date` tEXt chunk, PyMuPDF `/ID`) so re-runs produce byte-identical sample data. Override to roll the corpus to a new timestamp. |

## Where each setting lives

- **Static defaults**: [`backend/core/config.py`](https://github.com/dyh1265/RAG/blob/master/backend/core/config.py)
- **Local override**: copy [`.env.example`](https://github.com/dyh1265/RAG/blob/master/.env.example) → `.env`, edit, never commit.
- **CI override**: `env:` blocks in [`.github/workflows/ci.yml`](https://github.com/dyh1265/RAG/blob/master/.github/workflows/ci.yml) and [`.github/workflows/eval.yml`](https://github.com/dyh1265/RAG/blob/master/.github/workflows/eval.yml).
- **Docker override**: `environment:` in [`docker/docker-compose.yml`](https://github.com/dyh1265/RAG/blob/master/docker/docker-compose.yml).
