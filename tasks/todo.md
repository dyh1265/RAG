# GitHub publication cleanup

- [x] Sanitize `.env` (rotated key, placeholder restored) — USER must verify rotation at OpenAI
- [x] Purge artifacts: `advanced_rag.egg-info/`, `.pytest_cache/`, all `__pycache__/`, `notebooks/.ipynb_checkpoints/`, `notebooks/data/`, `phases/phase_05_evaluation/reports/`, `frontend/dist/`, `frontend/node_modules/`
- [x] Rewrite `.gitignore` (anchor eval paths properly, add tooling/OS/editor caches, whitelist demo PDFs)
- [x] Delete one-off migration scripts (`scripts/fix_phase_paths.py`, `scripts/restore_phase_imports.py`)
- [x] Add `LICENSE` (MIT)
- [x] Add `CONTRIBUTING.md`, `SECURITY.md`, `.github/PULL_REQUEST_TEMPLATE.md`
- [x] Add `.github/workflows/ci.yml` (pytest + ruff, py3.11/3.12 matrix)
- [x] Polish `pyproject.toml` (authors, license, readme, urls, classifiers, ruff per-file-ignores)
- [x] Polish `README.md` (badges, mermaid arch diagram, fixed step numbering 1..10, License + Sample data + Contributing sections)
- [x] Delete 19 empty/unused scaffold folders under `capstone/`, `docker/`, `phases/`
- [x] Fix real bug in `capstone/ui.py` (missing `DocuMind`/`DocuMindConfig` imports — F821)
- [x] Fix mis-placed import in `phases/phase_01_multimodal_ingestion/parsers/figure_parser.py`
- [x] Add `tests/{phase1..6,capstone}/__init__.py` so pytest can collect `test_metrics.py` in both phase3 and phase5

## Review

### Verification

- `git add -A` → **247 tracked files**, **~5.95 MB total** (vs the worst-case ~1.5 GB if junk had been committed).
- `.env` not tracked. No `sk-(proj|live)-` patterns in any tracked file.
- 0 empty directories remain outside `.git/` and `data/`.
- `ruff check .` → **All checks passed.**
- `pytest tests/ -m "not integration"` → **101 pass, 6 fail, 3 deselected**.
- Test collection: **107/110 collect with 0 errors** (was broken by `test_metrics.py` basename clash before this cleanup).

### Pre-existing test failures (not in scope, not introduced)

| Test | Cause |
|---|---|
| `tests/phase1/test_answer_generator.py::test_generate_openai_calls_api_and_builds_citations` | OpenAI client init in test fixture |
| `tests/phase1/test_answer_generator.py::test_generate_openai_requires_api_key` | OpenAI client init in test fixture |
| `tests/phase3/test_fingerprint.py::test_doc_fingerprint_changes_on_write` | Flaky: both `write_bytes` happen within the same `mtime_ns` on fast machines |
| `tests/phase5/test_metrics.py::test_sample_passed_retrieval_only` | Assertion on metric value |
| `tests/test_pipeline.py::test_ingest_parses_embeds_and_upserts` | Hard-codes `\data\report.pdf` which resolves to `C:\data\report.pdf` |
| `tests/test_pipeline.py::test_query_generates_answer` | MagicMock chain bypasses `.answer` via `model_copy()` |

None touch files modified in this cleanup. Pre-existing, should be tracked as separate issues.

### Behavior diff

- **Imports / runtime:** None except the genuine bug fix (`capstone/ui.py` now actually imports `DocuMind`/`DocuMindConfig` — previously crashed at module load).
- **Test discovery:** Was broken (collection error), now works (10 phase-scoped test packages namespaced).
- **CI:** New — runs pytest + ruff on push/PR for Python 3.11 + 3.12.
- **Repo layout:** 19 empty scaffold folders gone; no production code paths touched.

### Residual risks

- **The leaked OpenAI key in the working-tree `.env` before sanitization is compromised.** Even though `.env` was never committed (no `.git/` existed pre-cleanup), the key could have been keylogged, screenshotted, or otherwise leaked locally. USER must finish rotation at https://platform.openai.com/api-keys.
- **6 pre-existing test failures** ride along into the first commit. CI will be red on the first push until they're fixed or excluded. Quick mitigation: add `-k "not (test_generate_openai or test_doc_fingerprint_changes_on_write or test_sample_passed_retrieval_only or test_ingest_parses_embeds or test_query_generates_answer)"` to the CI step, or mark them `@pytest.mark.xfail` — but I did NOT do that here because silently skipping broken tests is worse than visible red CI.
- **`pyproject.toml` repo URLs** point to `github.com/dyh/advanced-rag` — confirm/replace with the real org+repo before pushing.
- **LICENSE copyright holder** is currently `DYH` — replace with full legal name if desired.
- **`frontend/package-lock.json`** is large (61 KB) but expected; not a concern.

### Files added (12)

- `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`
- `.github/workflows/ci.yml`, `.github/PULL_REQUEST_TEMPLATE.md`
- `tests/phase1/__init__.py`, `tests/phase2/__init__.py`, `tests/phase3/__init__.py`, `tests/phase4/__init__.py`, `tests/phase5/__init__.py`, `tests/phase6/__init__.py`, `tests/capstone/__init__.py`

### Files modified (5)

- `.env` (key redacted), `.gitignore` (rewritten), `pyproject.toml` (metadata + ruff config), `README.md` (badges, diagram, numbering, License section), `capstone/ui.py` (missing imports), `phases/phase_01_multimodal_ingestion/parsers/figure_parser.py` (import placement)

### Files / folders deleted

- `scripts/fix_phase_paths.py`, `scripts/restore_phase_imports.py`
- 19 empty scaffold directories (7 under `capstone/`, 2 under `docker/`, 10 under `phases/`)
- All build/cache artifacts on disk (gitignored anyway, but cleared from working tree)

### Would a staff engineer approve this?

Yes — with one caveat: the 6 pre-existing test failures should be triaged before tagging v0.1.0 publicly, otherwise the CI badge stays red. The cleanup itself is minimal, root-cause oriented (real bug fix in `capstone/ui.py`, real lint fix in `figure_parser.py`, real test-collection fix via `__init__.py`s), and adds no unnecessary scaffolding.
