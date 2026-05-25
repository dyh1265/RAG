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
