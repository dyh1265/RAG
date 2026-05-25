# Phase 2 — Long-document retrieval

**Status:** ~95% — chunking, section paths, hybrid retrieval, parent-expand, semantic chunker, FlashRank, and exit test automation.

**Exit test (target):** 200+ page PDF; section-specific questions retrieve correct distant pages.

## What's wired

| Feature | Flag / env | When |
|---------|------------|------|
| Section paths from PDF headings | default on | ingest |
| Context prefix before embed | default on | ingest |
| Recursive text chunking | `--recursive-chunk` / `USE_RECURSIVE_CHUNKER=true` | ingest |
| Semantic chunking | `--semantic-chunk` / `USE_SEMANTIC_CHUNKER=true` | ingest |
| BM25 + dense hybrid (text only) | `--hybrid` / `USE_HYBRID=true` | query |
| Parent→child expand | default on / `--no-parent-expand` | query |
| FlashRank reranker | `--flashrank` / `USE_FLASHRANK=true` | query |
| Cross-encoder rerank (Phase 1) | `--rerank` | query |

Phase 1 multimodal retrieval (figures, tables, ColPali pages) is unchanged. Hybrid replaces the **text_chunks** leg only.

## Install

```bash
# From project root (not docker/)
pip install -e ".[phase2]"
```

GPU Docker includes Phase 2 deps after rebuild. If using `phase1-gpu-shell` with mounted source, recreate the container after compose changes:

```bash
cd docker
docker compose --profile phase1-gpu up -d qdrant phase1-gpu-shell --force-recreate
```

Or install deps once inside a running shell:

```bash
docker compose exec phase1-gpu-shell pip install rank-bm25 langchain-text-splitters tiktoken flashrank
```

## Demo

```bash
python phases/phase_01_multimodal_ingestion/demo.py \
    --doc data/raw/sample_report.pdf \
    --query "What was Q4 2024 revenue and operating margin?" \
    --hybrid --recursive-chunk \
    --provider openai
```

Long document (812-page Sommerville textbook):

```bash
python phases/phase_01_multimodal_ingestion/demo.py \
    --doc data/raw/long_report.pdf \
    --query "What is a baseline in configuration management?" \
    --hybrid --recursive-chunk --retrieve-only --provider openai
```

Re-ingest after enabling Phase 2 options so vectors include `section_path` and `context_prefix`.

## Docker

Requires Qdrant: `docker compose up -d qdrant` from `docker/`.

**CPU — sample report demo (Phase 2 flags):**

```bash
cd docker
docker compose --profile phase1 run --rm phase1-demo \
    --doc data/raw/sample_report.pdf \
    --query "What was Q4 2024 revenue and operating margin?" \
    --hybrid --recursive-chunk --retrieve-only --provider openai
```

**GPU — long-doc exit test** (812-page ingest; use `USE_COLPALI=false` for text-only speed):

```bash
cd docker
docker compose --profile phase1-gpu up -d qdrant

# One-shot (override demo entrypoint)
docker compose --profile phase1-gpu run --rm \
    -e USE_COLPALI=false \
    --entrypoint python \
    phase1-demo-gpu \
    phases/phase_02_long_doc_retrieval/run_exit_test.py \
    --hybrid --recursive-chunk --min-recall 0.75

# Re-run queries only (after ingest)
docker compose --profile phase1-gpu run --rm \
    -e USE_COLPALI=false \
    --entrypoint python \
    phase1-demo-gpu \
    phases/phase_02_long_doc_retrieval/run_exit_test.py \
    --hybrid --recursive-chunk --skip-ingest
```

**GPU warm shell** (faster repeat runs after first ingest):

```bash
docker compose --profile phase1-gpu up -d qdrant phase1-gpu-shell

# First time: ingest + exit test
docker compose exec phase1-gpu-shell env USE_COLPALI=false \
    python phases/phase_02_long_doc_retrieval/run_exit_test.py \
    --hybrid --recursive-chunk

# Later: query only
docker compose exec phase1-gpu-shell env USE_COLPALI=false \
    python phases/phase_02_long_doc_retrieval/run_exit_test.py \
    --hybrid --recursive-chunk --skip-ingest
```

If the image predates Phase 2 deps: `docker compose exec phase1-gpu-shell pip install flashrank rank-bm25 langchain-text-splitters tiktoken`

## Exit test (host)

Automated page-recall benchmark on `data/raw/long_report.pdf`:

```bash
# Requires Qdrant running; first run ingests ~812 pages (slow)
python phases/phase_02_long_doc_retrieval/run_exit_test.py \
    --hybrid --recursive-chunk --min-recall 0.75

# Re-run queries only
python phases/phase_02_long_doc_retrieval/run_exit_test.py \
    --hybrid --recursive-chunk --skip-ingest
```

Benchmark Q&A: `data/benchmarks/long_doc_qa.json`

## Components

| Module | Role |
|--------|------|
| `chunking/recursive_chunker.py` | LangChain recursive splitter for large text blocks |
| `chunking/semantic_chunker.py` | Embedding-similarity breakpoints for topic-aware splits |
| `enrichment/section_paths.py` | Heading detection → `section_path` |
| `enrichment/context_enricher.py` | `context_prefix` from title + section |
| `retrieval/hybrid_retriever.py` | BM25 + dense RRF for `text_chunks` (cached BM25 per doc) |
| `retrieval/parent_expand.py` | Expand child hits to parent chunks |
| `retrieval/flashrank_reranker.py` | Lightweight FlashRank reranker |
| `benchmark.py` | Page-recall scoring for exit test |
| `run_exit_test.py` | CLI exit test runner |
| `ingest.py` | Post-parse Phase 2 orchestration |

## Not built yet

- Hierarchical section paths (multi-level `"2.3 > Risk Factors"`)
- Proposition / late chunking strategies

See [`tasks/todo.md`](../tasks/todo.md).
