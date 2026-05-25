# Phase 5 — Evaluation

**Status:** Golden set eval with retrieval metrics, HTML reports, index check, optional RAGAS, regression baselines.

**Exit test (target):** `run_full_eval.py` produces HTML report + baseline + regression alerts on real answers.

## Install

```bash
pip install -e ".[phase5]"
```

Phase 5 adds `jinja2` for HTML reports. RAGAS metrics are optional (`--ragas`, requires OpenAI API key).

## Golden set

`data/benchmarks/golden_qa.json` — 15 samples:

| Tag | Doc | Count |
|-----|-----|-------|
| `sample-report` | `sample_report.pdf` | 6 (text, table, figure) |
| `long-doc` | `long_report.pdf` | 9 |

## Run evaluation

**Retrieval-only** (no LLM, good for CI / Docker):

```bash
python phases/phase_05_evaluation/run_full_eval.py \
    --system phase_02 \
    --retrieve-only \
    --hybrid --recursive-chunk \
    --ingest-if-missing \
    --tag long-doc
```

**Docker (long-doc retrieval, warm shell):**

```powershell
cd docker
docker compose --profile phase1-gpu up -d qdrant phase1-gpu-shell
docker compose exec phase1-gpu-shell env USE_COLPALI=false python phases/phase_05_evaluation/run_full_eval.py --system phase_02 --retrieve-only --hybrid --recursive-chunk --ingest-if-missing --tag long-doc
```

Use `--allow-partial` to write reports without exiting non-zero when some samples fail.

**Full eval with OpenAI answers + RAGAS:**

```bash
python phases/phase_05_evaluation/run_full_eval.py \
    --system phase_02 \
    --provider openai \
    --hybrid --recursive-chunk \
    --ingest-if-missing \
    --ragas \
    --save-baseline
```

Reports land in `phases/phase_05_evaluation/reports/` (JSON + HTML). Baselines in `phases/phase_05_evaluation/baselines/`.

## Metrics

| Metric | Meaning |
|--------|---------|
| `retrieval_page_recall` | Top-k hit within `page_tolerance` of expected page(s) |
| `retrieval_chunk_type_recall` | Retrieved expected modality (table/figure) |
| `context_keyword_recall` | Ground-truth keywords present in retrieved context |
| `faithfulness` | Heuristic: answer sentences supported by context (skipped with `--retrieve-only`) |
| `ragas_faithfulness` | RAGAS faithfulness when `--ragas` + OpenAI key |
| `answer_keyword_overlap` | Ground-truth keywords in generated answer |
| `latency_ms` | End-to-end per sample (reported, not a pass gate) |

Pass/fail uses retrieval metrics + faithfulness threshold (`eval_faithfulness_threshold` in config). Retrieve-only mode skips the faithfulness gate.

## CLI flags

| Flag | Purpose |
|------|---------|
| `--ingest-if-missing` | Ingest PDFs from golden set before eval |
| `--retrieve-only` | Skip LLM generation; retrieval metrics only |
| `--ragas` | Add RAGAS faithfulness + answer relevancy |
| `--save-baseline` | Write aggregate metrics for regression checks |
| `--fail-on-regression` | Exit 1 when metrics drop vs baseline |
| `--allow-partial` | Exit 0 even if some samples fail |
| `--no-fail-on-error` | Continue when a sample raises an exception |

## Not built yet

- Grow golden set to 50+ samples
- CI regression gate in GitHub Actions
- Taxonomy-tagged samples (Phase 4)

See [`tasks/todo.md`](../tasks/todo.md).
