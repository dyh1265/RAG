# DocuMind Phase Notebooks

Six Jupyter notebooks walk through the Advanced RAG project from multimodal ingestion through production API.

| Notebook | Phase | Topics |
|----------|-------|--------|
| [01_multimodal_ingestion.ipynb](01_multimodal_ingestion.ipynb) | 1 | PDF parsing, chunk types, embeddings, Qdrant, RRF retrieval |
| [02_long_doc_retrieval.ipynb](02_long_doc_retrieval.ipynb) | 2 | Chunking, section paths, BM25+dense hybrid, parent expand, reranking |
| [03_scalable_ingestion.ipynb](03_scalable_ingestion.ipynb) | 3 | Redis cache, dedup, Celery bulk ingest, Prometheus metrics |
| [04_taxonomy_generation.ipynb](04_taxonomy_generation.ipynb) | 4 | RDF ontology, fuzzy linking, conformity scoring |
| [05_evaluation.ipynb](05_evaluation.ipynb) | 5 | Golden set, retrieval metrics, HTML reports, baselines |
| [06_production_api.ipynb](06_production_api.ipynb) | 6 | FastAPI, PII redaction, rate limits, tracing |

## Setup

Run **`pip install` from the project root** (`RAG/`), not from `docker/`:

```powershell
cd C:\Users\dyh\Desktop\RAG
pip install -e ".[phase1,phase2,notebooks]"
python -m jupyterlab notebooks/
```

On Windows, `jupyter` may not be on PATH even after install. Always use `python -m jupyterlab` (or `py -m jupyterlab`).

Optional extras per phase: `phase3`, `phase4`, `phase5`, `phase6`.

## Infrastructure

Most runnable cells expect Docker services:

```bash
cd docker
docker compose up -d qdrant redis
docker compose --profile production up -d rag-api   # Phase 6 only
```

Cells degrade gracefully when Qdrant or the API is offline — they still show types, imports, and static examples.

## Related docs

- [Root README](../README.md)
- [documind package](../documind/README.md)
- Phase READMEs under `phases/phase_*/README.md`
