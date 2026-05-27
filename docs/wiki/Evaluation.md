# Evaluation

A RAG system that isn't evaluated is mostly guesswork. DocuMind ships a small, hand-curated golden set and runs the same metrics in CI, the eval workflow, and any local checkout — so a regression is caught before it gets merged.

## Golden set

[`tests/eval/golden_set.jsonl`](https://github.com/dyh1265/RAG/blob/master/tests/eval/golden_set.jsonl) is a JSONL of cases over [`data/raw/sample_report.pdf`](https://github.com/dyh1265/RAG/blob/master/data/raw/sample_report.pdf) — a synthetic but realistic annual report with text, a table, and a figure across three pages. The sample PDF is byte-reproducible (see [Configuration → SOURCE_DATE_EPOCH](Configuration)).

Each row looks like:

```json
{
  "id": "fig3-q4",
  "query": "What was Q4 2024 revenue according to Figure 3?",
  "doc_id": "ed7d53f9b08caa39",
  "source_pdf": "data/raw/sample_report.pdf",
  "relevant_pages": [2],
  "reference_answer": "Q4 2024 revenue was $54.6M.",
  "key_phrases": ["54.6", "Q4 2024"]
}
```

The 10 cases deliberately span all three retrieval modalities:

| Topic | Modality the answer lives in |
|---|---|
| Total revenue, NRR, FCF | text (page 1) |
| Quarterly revenue trend, DataPulse | figure caption + body (page 2) |
| Q3 margin, Q1 2025 row, board target | table (page 3) |

If a code change improves text retrieval but breaks figure retrieval, the metrics shift visibly — that's the whole point of the modality coverage.

## Metrics

Implemented in [`tests/eval/metrics.py`](https://github.com/dyh1265/RAG/blob/master/tests/eval/metrics.py):

| Metric | What it asks |
|---|---|
| **Recall@5** | "Of the pages that should appear, how many did we return in the top 5?" Averaged across the golden set. |
| **Hit@5** | "Did at least one relevant page appear in the top 5?" Binary per case, averaged. The simplest "did we find anything useful?" signal. |
| **MRR** | Reciprocal rank of the first relevant page. Penalizes burying the right answer behind irrelevant ones. |
| **Keyword coverage** | Fraction of `key_phrases` that appear in the generated answer. Cheap proxy for faithfulness without an LLM judge. |
| **p95 retrieval latency (ms)** | After dropping the first cold query for warmup, p95 of the retrieve-only wall clock. Catches an O(N²) regression before it ships. |
| **Faithfulness (Ragas)** | Optional, gated by `pip install -e ".[eval]"` and `RUN_RAGAS_EVAL=1`. Uses an LLM judge to score whether the answer is grounded in the retrieved contexts. |

## CI gates

The thresholds live next to the application config so the same numbers are honoured in CI, the eval workflow, the API, and local runs:

```python
# backend/core/config.py
eval_recall_at_5_threshold: float = 0.70
eval_hit_at_5_threshold: float = 0.80
eval_mrr_threshold: float = 0.50
eval_keyword_coverage_threshold: float = 0.66
eval_faithfulness_threshold: float = 0.85
eval_retrieval_latency_p95_ms: float = 60_000.0
```

The eval test fails (red CI) if any of these aren't met:

```python
# tests/eval/test_retrieval.py
assert scores["recall_at_5"] >= limits["recall_at_5"]
assert scores["hit_at_5"]    >= limits["hit_at_5"]
assert scores["mrr"]         >= limits["mrr"]
assert scores["retrieve_p95_ms"] <= limits["retrieval_latency_p95_ms"]
```

Every threshold is also exposed as a `EVAL_*` env var so a flaky CPU runner can be tuned without rewriting the test.

## Workflows

Two workflows run the eval, gated to keep CI cost predictable:

| Workflow | When it runs | What it does |
|---|---|---|
| [`eval.yml` → `retrieval-eval`](https://github.com/dyh1265/RAG/blob/master/.github/workflows/eval.yml) | Weekly cron, every push touching `backend/retrieval/`, `backend/ingestion/`, `tests/eval/`, or `backend/core/pipeline.py`, and on demand | Spins up Qdrant as a service container, regenerates the sample PDF reproducibly, ingests it, runs the retrieval eval, **emits a Markdown benchmark summary** to the GitHub Actions run page, and uploads `benchmarks.md` as an artifact. |
| [`eval.yml` → `answer-eval`](https://github.com/dyh1265/RAG/blob/master/.github/workflows/eval.yml) | Same triggers, gated on `OPENAI_API_KEY` repo secret | Adds a real OpenAI generation pass on top of the retrieved contexts and checks `keyword_coverage` against the threshold. |

The secret gate uses a small `check-secrets` job whose `has_openai_key` output the `answer-eval` job consumes via `needs:` — the documented workaround for [GitHub Actions not reliably evaluating `secrets.*` inside `if:`](https://docs.github.com/en/actions/security-guides/encrypted-secrets#using-encrypted-secrets-in-a-workflow).

## Adding a golden case

1. Decide what the case tests (a metric, a modality, a corner case).
2. Append a JSON line to [`tests/eval/golden_set.jsonl`](https://github.com/dyh1265/RAG/blob/master/tests/eval/golden_set.jsonl). `doc_id` must match the deterministic doc ID produced by [`stable_doc_id`](https://github.com/dyh1265/RAG/blob/master/backend/ingestion/parsers/base_parser.py) for the source PDF — easiest is `python -c "from backend.ingestion.parsers.base_parser import stable_doc_id; print(stable_doc_id('data/raw/sample_report.pdf'))"`.
3. Run `pytest tests/eval/test_retrieval.py -m eval -v` locally with Qdrant up.
4. If the case fails, decide whether the case is unreasonable (drop it) or whether retrieval has a real gap (fix it).

## Reproducing the benchmarks locally

```bash
( cd docker && docker compose up -d qdrant )
python scripts/generate_sample_report.py      # one-off, also tracked in git
pytest tests/eval/test_retrieval.py tests/eval/test_metrics.py -m eval -v
```

If you want the formatted Markdown table the workflow produces:

```bash
python scripts/run_eval_report.py             # prints to stdout
python scripts/run_eval_report.py -o bench.md # also writes to file
```

That same script is what publishes `benchmarks.md` as an artifact in CI.
