# Phase 1 — Multimodal ingestion (current state)

**Status:** ~100% complete — ingest, CLIP figures, ColPali pages, RRF retrieval, optional reranker, answer generation.  
**Exit test:** Table and chart questions hit the **correct chunk types** on the sample report.

This document describes **what the code does today**. When Phase 1 items in [`tasks/todo.md`](../tasks/todo.md) are completed, update this file in the same change.

---

## What works today

The demo CLI wraps **`shared.pipeline.RAGPipeline`** — the same entry point eval and API will use.

1. **Ingest** — `RAGPipeline.ingest(path)` → parse, embed, Qdrant upsert
2. **Query** — `RAGPipeline.query(QueryRequest)` → retrieve → optional rerank → optional answer

There is **no LLM in the Docker image**. Use `--retrieve-only` in Docker, or run hybrid with local Ollama/OpenAI.

```
┌─────────┐   IngestionPipeline   ┌────────────────┐   embed    ┌──────────────┐
│   PDF   │ ────────────────────► │ text + table   │ ─────────► │ Qdrant         │
└─────────┘  PDFTextParser         │ + figure chunks│   bge-m3   │ text_chunks    │
             TableParser           │ + page images  │   (1024)   │ table_chunks   │
             FigureParser           └────────────────┘            │ page_chunks    │
             PageImageParser         ┌────────────────┐            │                │
                                     │ figure PNGs    │ ─────────► │ figure_chunks  │
                                     └────────────────┘   CLIP     │   (512-dim)    │
                                                        (512-dim)  └──────┬───────┘
                                                                          │
┌─────────┐   bge-m3 + CLIP query vectors   per-collection search + weighted RRF │
│ question│ ─────────────────────────────────────────────────────────────────────┘
└─────────┘                                              │
                                                           ▼
                                              print top-k chunks (type + page)
```

---

## Ingest (indexing)

**Entry point:** `ingest()` in `demo.py` → `IngestionPipeline`

| Step | Component | What happens |
|------|-----------|--------------|
| 1 | `PDFTextParser` | PyMuPDF layout text blocks → `ChunkType.TEXT` |
| 2 | `TableParser` | pdfplumber ruled tables → `ChunkType.TABLE` |
| 3 | `FigureParser` | Crop embedded images → PNG + captions → `figure_chunks` |
| 4 | `PageImageParser` | Full-page PNG per page → `page_chunks` (for ColPali path) |
| 5 | `embed_chunks()` | Text/table → bge-m3; figures → CLIP; pages → ColPali when `--colpali` (128-dim pooled) |
| 6 | `QdrantStore.upsert()` | Routes by `COLLECTION_MAP`; recreates collection if vector dimension changes |

**Sample output:**

```
[ingest] Extracted 14 chunks from sample_report.pdf (1 figure, 3 page_image, 1 table, 9 text)
[ingest] Upserted 14 vectors into Qdrant (1 → figure_chunks, 3 → page_chunks, 1 → table_chunks, 9 → text_chunks)
```

Regenerate the sample PDF (includes a **ruled table** on page 3 for pdfplumber):

```bash
python scripts/generate_sample_report.py
```

---

## Query (retrieval)

**Entry point:** `query()` in `demo.py` → `MultiModalRetriever`

| Step | What happens |
|------|--------------|
| 1 | Question embedded with bge-m3 (text/table/page) and CLIP text encoder (`figure_chunks`) |
| 2 | Each collection searched independently with the matched vector |
| 3 | Results fused with **weighted RRF** (figure/chart hints boost `figure_chunks`; table/margin hints boost `table_chunks`) |
| 4 | Dedupe duplicate caption text; prefer `figure` / `table` over `text` / `page_image` |
| 5 | Chunk type, text, page number, and RRF score printed |

**Sample queries on `sample_report.pdf`:**

| Query | Top result |
|-------|------------|
| "What does Figure 3 show about revenue trends?" | `type=figure` page 2 |
| "What was Q4 2024 revenue and operating margin?" | `type=table` page 3 |

Use `--skip-ingest` when the PDF is already indexed.

---

## Components

| File | Role |
|------|------|
| `parsers/pdf_text_parser.py` | PDF → text blocks (`ChunkType.TEXT`) |
| `parsers/table_parser.py` | PDF → tables via pdfplumber (`ChunkType.TABLE`) |
| `parsers/figure_parser.py` | PDF → cropped figures + captions (`ChunkType.FIGURE`) |
| `parsers/page_image_parser.py` | PDF → full-page PNGs (`ChunkType.PAGE_IMAGE`) |
| `parsers/base_parser.py` | Parser interface, `stable_doc_id`, `stable_chunk_id` |
| `ingestion_pipeline.py` | Runs all parsers, merges chunks |
| `embeddings/text_embedder.py` | HuggingFace `BAAI/bge-m3` via sentence-transformers (1024-dim) |
| `embeddings/image_embedder.py` | OpenCLIP ViT-B-32 for figure PNGs + CLIP query encoding (512-dim) |
| `embeddings/colpali_embedder.py` | ColQwen2 for page PNGs + query encoding (128-dim mean-pooled) |
| `embeddings/multimodal_embed.py` | Route ingest embedding by chunk type |
| `retrieval/multimodal_retriever.py` | Per-collection search + weighted RRF fusion |
| `retrieval/reranker.py` | Optional `bge-reranker-v2-m3` cross-encoder rerank |
| `generation/answer_generator.py` | Ollama / OpenAI answer + citations |
| `stores/qdrant_store.py` | Collections, upsert, delete-by-doc, search |
| `shared/pipeline.py` | `RAGPipeline` — unified ingest/query spine |
| `demo.py` | CLI wrapper around `RAGPipeline` |

Shared models and config: `shared/models.py`, `shared/config.py`.

---

## Chunking

### Text (PyMuPDF)

Layout blocks by position/font — usually paragraphs, not sentences. Blocks &lt; 50 chars skipped.

### Tables (pdfplumber)

Ruled grids detected via line intersections (`page.find_tables()`). Each table becomes one chunk:

```
Quarter | Revenue ($M) | YoY Growth | Op. Margin
Q1 2024 | 42.1 | 12.3% | 19.8%
...
```

Requires actual table structure in the PDF (ruled grid on page 3 of the sample report).

### Figures (PyMuPDF)

Embedded images cropped to `data/processed/{doc_id}/figures/page{N}_fig{idx}.png`. Searchable `content` is built from nearby caption text. **Vectors** come from the cropped PNG via OpenCLIP (`ImageEmbedder`), not caption text. Optional OCR via `FigureParser(use_ocr=True)` when pytesseract is installed.

### Page images (PyMuPDF)

Each page rendered to `data/processed/{doc_id}/pages/page{N}.png` at 150 DPI. With **`--colpali`**, page vectors come from ColQwen2 visual embeddings (128-dim mean-pooled). Without it, pages use page text via bge-m3 (1024-dim).

---

## Qdrant

| Setting | Default |
|---------|---------|
| URL (host) | `http://localhost:6333` |
| URL (Docker demo) | `http://qdrant:6333` |
| Collections used now | `text_chunks`, `table_chunks` (1024-dim), `figure_chunks` (512-dim CLIP), `page_chunks` (1024-dim text **or** 128-dim ColPali) |
| Dashboard | http://localhost:6333/dashboard |

**Versions (pinned):** server `v1.12.5`, client `>=1.12.0,<1.13.0`.

---

## Hugging Face

**Loaded at runtime:**

- [`BAAI/bge-m3`](https://huggingface.co/BAAI/bge-m3) — text, table chunks; page chunks when ColPali off
- OpenCLIP ViT-B-32 (LAION) — figure PNGs and figure queries
- [ColQwen2](https://huggingface.co/vidore/colqwen2-v1.0) — page PNGs when `--colpali` (or `vidore/colSmol-500M` on CPU)

**Configured but not loaded yet:** ColPali, reranker — see `shared/config.py`.

---

## Docker

**ColPali page retrieval (host or GPU Docker):**

```bash
# GPU Docker (NGC PyTorch base, NVIDIA required) — USE_COLPALI=true in image
cd docker
docker compose --profile phase1-gpu up -d qdrant
docker compose --profile phase1-gpu build phase1-demo-gpu
docker compose --profile phase1-gpu run --rm phase1-demo-gpu \
    --doc data/raw/sample_report.pdf \
    --query "What does Figure 3 show?" \
    --provider openai
```

**ColPali on host:**

```bash
# Re-ingest required after enabling (page_chunks dimension changes 1024 → 128)
python phases/phase_01_multimodal_ingestion/demo.py \
    --doc data/raw/sample_report.pdf \
    --query "What does Figure 3 show?" \
    --colpali \
    --provider openai
```

On CPU-only hosts, set `COLPALI_MODEL=vidore/colSmol-500M` in `.env`.

**ColPali vs CPU ingest:** `page_chunks` dimension changes (1024-dim bge-m3 text vs 128-dim ColPali). After enabling ColPali in GPU Docker, **re-ingest without `--skip-ingest`** so Qdrant recreates `page_chunks`. The demo only warns when Qdrant's stored dimension actually mismatches query mode.

**Model preload:** By default the demo loads all embedders before querying and prints `[preload] …`. Use `--skip-preload` only inside a warm shell where models are already in memory.

**Warm GPU shell** (fast query loops without cold-start per container):

```bash
cd docker
docker compose --profile phase1-gpu up -d qdrant phase1-gpu-shell
docker compose exec phase1-gpu-shell python phases/phase_01_multimodal_ingestion/demo.py \
    --doc data/raw/sample_report.pdf \
    --query "What was Q4 2024 revenue and operating margin?" \
    --provider openai --skip-ingest --skip-preload
```

```bash
cd docker
docker compose --profile phase1 up -d qdrant ollama
docker compose exec ollama ollama pull llama3.2   # once
docker compose --profile phase1 run --rm phase1-demo \
    --doc data/raw/sample_report.pdf \
    --query "What does Figure 3 show about revenue trends?" \
    --provider ollama \
    --skip-ingest
```

**Retrieve only** (skip LLM): add `--retrieve-only`.

**Hybrid — Ollama on host:**

```bash
ollama pull llama3.2
cd ..   # project root
python phases/phase_01_multimodal_ingestion/demo.py \
    --doc data/raw/sample_report.pdf \
    --query "What does Figure 3 show about revenue trends?" \
    --provider ollama \
    --rerank
```

Inside Docker, `phase1-demo` reaches Ollama at `http://ollama:11434` (set in `docker-compose.yml`).

CPU image (`Dockerfile.phase1`): PyMuPDF, pdfplumber, sentence-transformers, open_clip_torch, httpx, qdrant-client.

GPU image (`Dockerfile.phase1.gpu`): NGC `nvcr.io/nvidia/pytorch:25.02-py3` + pinned HF stack (transformers 5.x, colpali-engine 0.3.16).

---

## Tests

```bash
# Fast unit tests (no PDF, no models, no network)
pytest tests/phase1/ -v -m "not integration"

# Include parser integration tests (needs data/raw/sample_report.pdf)
pytest tests/phase1/ -v
```

---

## Known limitations

| Limitation | Why |
|------------|-----|
| ColPali mean-pooling | Full MaxSim multi-vector search not in Qdrant yet; patches are mean-pooled to one vector |
| ColPali GPU Docker | NGC PyTorch 25.02+ (`nvcr.io/nvidia/pytorch:25.02-py3`); 24.12 breaks transformers 5.x |
| ColPali size/speed | ColQwen2 is large; use colSmol-500M on CPU; GPU Docker recommended for ColPali |
| No ColPali page vectors | `page_chunks` still use page text via bge-m3 |
| Keyword-based collection boost | Figure/table hints are simple substring rules, not a classifier |
| Rank overlap | Duplicate caption text may still appear as separate chunks after dedupe |
| Layout text chunks | Headings may be filtered; Phase 2 adds `section_path` |

---

## Not built yet (Phase 1 todo)

See [`tasks/todo.md`](../tasks/todo.md):

- Wire Phase 6 API lifespan to pipeline (Phase 6 scope)

Phase 1 core + polish is complete.

---

## Documentation maintenance

When completing Phase 1 todo items:

1. Update this file (scope, diagrams, limitations).
2. Update the Phase 1 row in `tasks/todo.md` snapshot.
3. Adjust `README.md` quick start only if run instructions change.
