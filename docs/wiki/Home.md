# DocuMind Wiki

> Upload a PDF, chat with it, get cited answers — backed by hybrid retrieval, multimodal embeddings, and a CI-gated evaluation suite.

This wiki is the long-form companion to the [project README](https://github.com/dyh1265/RAG). The README answers *"how do I run it?"*; the wiki answers *"how does it work, and why?"*.

## What DocuMind is

DocuMind is a production-style Retrieval-Augmented Generation (RAG) system over PDFs. The same pipeline indexes text passages, tables, and figures into separate Qdrant collections, retrieves across all of them at query time, fuses the results, and asks an LLM (OpenAI or local Ollama) to answer with inline citations grounded in the retrieved chunks.

It is not a toy notebook. The repo ships with:

- A FastAPI service (`backend.api`) with rate limiting, PII redaction, taxonomy guardrails, and OpenTelemetry tracing.
- A React + Vite frontend (`frontend/`) that uploads documents, chats, and renders source citations.
- A Celery worker (`backend.scaling`) for bulk-ingest jobs with Redis-backed dedup and progress tracking.
- A Docker Compose stack with Qdrant, Redis, Prometheus, Grafana, and Jaeger.
- A reproducible eval suite (`tests/eval/`) with a hand-curated golden set and CI thresholds for recall@5, hit@5, MRR, and p95 retrieval latency.

## Read the wiki in this order

| Page | Read when you want to |
|---|---|
| [Architecture](Architecture) | Understand the service topology and how requests flow end-to-end. |
| [RAG Pipeline](RAG-Pipeline) | Walk the ingest and query stages: parse → enrich → embed → store → retrieve → answer. |
| [Retrieval](Retrieval) | Go deep on hybrid (BM25 + dense), multimodal fusion (text/tables/figures/pages), parent expansion, and rerankers. |
| [Evaluation](Evaluation) | Understand the golden set, metric definitions, and how CI gates regressions. |
| [Configuration](Configuration) | Reference for every feature flag and environment variable. |

## When this design is a good fit

- The corpus is **structured documents** (PDFs with figures, tables, equations) — not just plain prose.
- You want **citations** the user can click through to the source page, not just an answer.
- You can tolerate a **multi-service stack** (Qdrant + Redis + an API and worker) in exchange for proper observability, dedup, and bulk-ingest semantics.
- You care about **evaluation** as a first-class concern, not an afterthought.

## When something else might be a better fit

- You have plain-text knowledge-base articles — a single-collection vector index and a small RAG library are probably overkill in reverse here.
- You need sub-100 ms p95 latency — the multimodal fusion + optional reranker stage is honest about its budget (see [Evaluation](Evaluation)).
- You need streaming token-by-token UX — currently the generator returns the full answer (extending to streaming is straightforward; see [`backend/generation/answer_generator.py`](https://github.com/dyh1265/RAG/blob/master/backend/generation/answer_generator.py)).

## Contributing to the wiki

Source lives at [`docs/wiki/`](https://github.com/dyh1265/RAG/tree/master/docs/wiki) in the main repo. Push there and the [`Wiki Sync`](https://github.com/dyh1265/RAG/actions/workflows/wiki.yml) workflow republishes this site. See [`docs/wiki/README.md`](https://github.com/dyh1265/RAG/blob/master/docs/wiki/README.md) for the publishing setup.
