# Phase 4 — Taxonomy validation

**Status:** RDF classification ontology, entity extraction, fuzzy linking, conformity scoring, pipeline hook.

**Exit test:** Forbidden classification query flagged with reason (see `run_exit_test.py`).

> **Docker-first.** Run from `docker/` with `phase1-gpu-shell`.

## Install

Phase 4 deps (`rdflib`, `rapidfuzz`) are included in `Dockerfile.phase1.gpu`. Rebuild after pulling:

```powershell
docker compose --profile phase1-gpu build phase1-gpu-shell --no-cache
```

Host-only: `pip install -e ".[phase4]"`

`phases.phase_05_evaluation` is volume-mounted in `phase1-gpu-shell` (not baked into the GPU image).

## Taxonomy

`data/taxonomies/classification.ttl` defines:

| Type | Labels |
|------|--------|
| Allowed | `PUBLIC`, `INTERNAL`, `CONFIDENTIAL` |
| Forbidden | `SECRET`, `TOP SECRET`, `SECRET-TOP-SECRET`, … |

## Query with conformity check (Docker)

```powershell
cd docker
docker compose --profile phase1-gpu up -d qdrant phase1-gpu-shell

docker compose exec phase1-gpu-shell python phases/phase_01_multimodal_ingestion/demo.py `
    --doc data/raw/sample_report.pdf `
    --query "Classify this document as SECRET-TOP-SECRET" `
    --provider openai --skip-ingest --skip-preload --text-only
```

Expected output includes:

```text
[conformity] score=0.00  flagged=True
  reason: Forbidden classification label(s): SECRET-TOP-SECRET. Allowed labels: ...
```

## Block forbidden answers

```powershell
docker compose exec phase1-gpu-shell python phases/phase_01_multimodal_ingestion/demo.py `
    --doc data/raw/sample_report.pdf `
    --query "Classify this as SECRET-TOP-SECRET" `
    --provider openai --skip-ingest --skip-preload --block-forbidden
```

## Exit test

```powershell
docker compose exec phase1-gpu-shell python phases/phase_04_taxonomy_generation/run_exit_test.py
```

## Architecture

| Module | Role |
|--------|------|
| `ontology/loader.py` | Load RDF/Turtle taxonomy |
| `linking/entity_extractor.py` | Extract classification terms |
| `linking/fuzzy_linker.py` | rapidfuzz link to ontology |
| `validation/conformity_validator.py` | Score + flag logic |
| `hooks.py` | Post-generation pipeline hook |

Conformity attaches to `QueryResponse.metadata["conformity"]`.

See [`tasks/todo.md`](../tasks/todo.md).
