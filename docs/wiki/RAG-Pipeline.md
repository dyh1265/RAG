# RAG Pipeline

DocuMind's single entry point is `RAGPipeline` in [`backend/core/pipeline.py`](https://github.com/dyh1265/RAG/blob/master/backend/core/pipeline.py). The API, the eval harness, and the Celery worker all call it instead of wiring `ingestion` and `retrieval` together by hand — that's what keeps the eval suite honest and the demo small.

The pipeline has two stages:

```
ingest:  parse → enrich → embed → store
query:   embed-question → retrieve → fuse → expand → rerank → answer
```

## Ingest stage

### 1. Parse

[`backend.ingestion.parsers`](https://github.com/dyh1265/RAG/tree/master/backend/ingestion/parsers) registers one parser per modality. The `ParserRegistry` dispatches by file extension and chunk type:

| Parser | Produces | Notes |
|---|---|---|
| `PDFTextParser` (PyMuPDF) | text chunks | Inherits section headings → `section_path` so context enrichment can carry the hierarchy through the prompt. |
| `TableParser` (pdfplumber) | table chunks | Detects ruled tables via line-intersection; falls back to text. |
| `FigureParser` | figure chunks | Caption-aware bounding boxes, with a label like `Figure 3: …` so labeled-asset retrieval can pick them up directly. |
| `PageImageParser` | page-image chunks | Only used when `USE_COLPALI=true`. Whole-page images for visual-token retrieval. |

Document IDs are deterministic. [`stable_doc_id()`](https://github.com/dyh1265/RAG/blob/master/backend/ingestion/parsers/base_parser.py) hashes the path *from the `raw/` anchor down*, after normalizing separators, so the same PDF re-ingested from a Windows host (`C:\…\raw\file.pdf`), a Linux container (`/app/data/raw/file.pdf`), or a relative path (`data/raw/file.pdf`) all upsert to the same Qdrant row instead of duplicating.

### 2. Enrich

[`backend.retrieval.preprocessing`](https://github.com/dyh1265/RAG/blob/master/backend/retrieval/preprocessing.py) runs at ingest time so the cost is paid once, not per query:

- `USE_RECURSIVE_CHUNKER` / `USE_SEMANTIC_CHUNKER`: choose token-aware vs. semantic-boundary chunking (`max_chunk_size=512`, `chunk_overlap=64`).
- `USE_SECTION_PATHS`: attach the heading chain (`Executive Summary > Key Highlights`) to each chunk.
- `USE_CONTEXT_ENRICHMENT`: pre-compute the small "[context] previous sentence + chunk + next sentence" block used to disambiguate retrieved fragments.
- `USE_PII_REDACTION_ON_INGEST`: Presidio + spaCy redact emails, phone numbers, etc. before they ever hit the vector store.

### 3. Embed

[`backend.ingestion.embeddings`](https://github.com/dyh1265/RAG/tree/master/backend/ingestion/embeddings) routes chunks to one of three embedders:

| Embedder | Default model | Used for |
|---|---|---|
| `TextEmbedder` | `BAAI/bge-m3` | text chunks |
| `ImageEmbedder` | `laion/CLIP-ViT-B-32-laion2B-s34B-b79K` | figure / table chunks (rendered as images) |
| `ColPaliEmbedder` | `vidore/colqwen2-v1.0` | page-image chunks (opt-in, GPU recommended) |

`embed_chunks` batches by modality and caches by chunk fingerprint in Redis (`embedding_cache_ttl_seconds = 7 days`), so a re-ingest of an unchanged PDF is essentially free.

### 4. Store

[`QdrantStore`](https://github.com/dyh1265/RAG/blob/master/backend/ingestion/stores/qdrant_store.py) writes one row per chunk into the matching collection (`text_chunks`, `table_chunks`, `figure_chunks`, `page_chunks`). Each row carries the `doc_id`, `source_path`, `page_number`, `chunk_type`, optional bounding box, and the section path — enough metadata for the frontend's "open the citation" action to deep-link into the PDF viewer.

## Query stage

### 1. Embed the question

The text embedder turns the question into a 1024-dim vector. If [`USE_HYBRID=true`](Configuration), the BM25 tokenizer also indexes it for sparse retrieval.

### 2. Retrieve across modalities

[`MultiModalRetriever`](https://github.com/dyh1265/RAG/blob/master/backend/retrieval/multimodal_retriever.py) queries each Qdrant collection in parallel. Query hints (e.g. *"according to Table 1"* or *"in Figure 3"*) boost the matching modality; otherwise it just searches all of them. The full retrieval algorithm — including RRF fusion and parent expansion — is documented on the [Retrieval](Retrieval) page.

### 3. Optional rerank

If [`USE_FLASHRANK=true`](Configuration) or `use_rerank=True`, a cross-encoder (default `BAAI/bge-reranker-v2-m3`) reranks the top-K results down to `reranker_top_n=3`. FlashRank is the lighter-weight option.

### 4. Answer

[`AnswerGenerator`](https://github.com/dyh1265/RAG/blob/master/backend/generation/answer_generator.py) builds a numbered context block:

```
[1] (page 2, text)
Executive Summary. Acme Corp delivered strong financial performance…

[2] (page 3, table)
Quarter | Revenue ($M) | YoY Growth | …
```

It then calls the configured LLM with a strict system prompt: *"Answer ONLY using the numbered context passages. Cite sources inline as [1], [2]"*. The response is wrapped in a `QueryResponse` with `Citation` objects that carry `doc_id`, `source_path`, `page_number`, `chunk_id`, and a trimmed excerpt — the frontend uses those to render clickable citation badges and open the source panel.

### 5. Guardrails

- **No context**: if zero chunks come back, the generator returns a friendly fallback ("This document may be image-only; re-upload to run OCR") instead of hallucinating.
- **Only non-substantive context**: if every retrieved chunk is e.g. an OCR-failed empty page, same fallback.
- **Taxonomy block**: with `TAXONOMY_BLOCK_FORBIDDEN=true`, an RDF taxonomy check can hard-block answers that mention forbidden classes; with `false`, it warns and annotates the response.

## Code map

| Concern | File |
|---|---|
| Pipeline entry point | [`backend/core/pipeline.py`](https://github.com/dyh1265/RAG/blob/master/backend/core/pipeline.py) |
| Request / response shapes | [`backend/core/models.py`](https://github.com/dyh1265/RAG/blob/master/backend/core/models.py) |
| Parsers | [`backend/ingestion/parsers/`](https://github.com/dyh1265/RAG/tree/master/backend/ingestion/parsers) |
| Embedders | [`backend/ingestion/embeddings/`](https://github.com/dyh1265/RAG/tree/master/backend/ingestion/embeddings) |
| Qdrant store | [`backend/ingestion/stores/qdrant_store.py`](https://github.com/dyh1265/RAG/blob/master/backend/ingestion/stores/qdrant_store.py) |
| Retrieval | [`backend/retrieval/`](https://github.com/dyh1265/RAG/tree/master/backend/retrieval) |
| Answer generator | [`backend/generation/answer_generator.py`](https://github.com/dyh1265/RAG/blob/master/backend/generation/answer_generator.py) |
| Bulk worker | [`backend/scaling/`](https://github.com/dyh1265/RAG/tree/master/backend/scaling) |
