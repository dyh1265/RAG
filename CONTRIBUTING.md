# Contributing

Thanks for your interest in improving DocuMind! This document covers the basics for getting set up and submitting changes.

## Development setup

```bash
# Clone, then from the repo root:
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env   # fill in OPENAI_API_KEY
```

For Docker-based workflows see the main [README](README.md).

## Running tests

```bash
# Fast unit tests (no external services required)
pytest tests/ -m "not integration" -v

# Module-scoped (mirrors backend/ layout)
pytest tests/ingestion/ -v
pytest tests/retrieval/ -v
pytest tests/scaling/ -v
pytest tests/taxonomy/ -v
pytest tests/api/ -v
pytest tests/eval/test_metrics.py -v
```

Integration tests require Qdrant + sample PDFs — start them with `docker compose up -d qdrant` from `docker/` first. RAG quality benchmarks live under `tests/eval/`; see the README *RAG quality eval* commands.

## Linting

```bash
pip install ruff
ruff check .
```

`ruff` settings live in [pyproject.toml](pyproject.toml) (`line-length = 100`, `py311`).

## Pull request guidelines

1. Branch from `main`. One logical change per PR.
2. Keep the diff focused; do not mix refactors with feature changes.
3. Add or update tests for behavior changes.
4. Update relevant docs (`README.md`, `deploy/README.md`, `frontend/README.md`) if you changed a public interface.
5. Run `pytest -m "not integration"` and `ruff check .` before pushing.
6. Fill out the PR template — especially the "How was this tested?" section.

## Commit messages

Conventional, imperative present tense:

```
retrieval: tighten hybrid retriever score fusion
docker: bump qdrant to 1.12.x
docs: clarify GPU prerequisites in README
```

## Reporting issues

Use the issue tracker. Include:
- Module / area affected (e.g. `backend.retrieval`, `frontend`, `docker`)
- Minimal reproduction (command, query, PDF if possible)
- Expected vs actual behavior
- Relevant logs (`docker compose logs <service>`)

## Security

Please do **not** open public issues for security vulnerabilities. See [SECURITY.md](SECURITY.md).
