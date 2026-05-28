# Fix Internal Server Error on /query (torch 2.5 + transformers 5.9)

- [x] Diagnose: docker logs show `ValueError` from `check_torch_load_is_safe` (torch 2.5.1+cu121, transformers 5.9)
- [x] Pin `torch>=2.6` in Dockerfile; GPU default index `cu124` (cu121 caps at 2.5.1)
- [x] Block startup until model warmup completes (or record failure in `/ready`)
- [x] `/query` returns 503 with actionable message on torch/transformers mismatch

## Review (after implementation)

- verification run: user must `docker compose ... build rag-api ingest-worker` and confirm `torch>=2.6` in container
- behavior diff notes: `/ready` reports `models: ok|warming|error`; warmup is awaited at startup; GPU default cu124
- residual risks: hosts without CUDA 12.4 driver may need different TORCH_INDEX_URL; first rebuild re-downloads wheels

---

# Generate the DocuMind reference book (PDF)

- [x] Read existing wiki + README + key source files to gather accurate content
- [x] Write `scripts/generate_book.py` — PyMuPDF book builder with cover, TOC, chapters, code blocks, notes, key-value tables, page headers/footers, bookmarks, deterministic metadata via `SOURCE_DATE_EPOCH`
- [x] Cover preface + 12 chapters (intro, architecture, ingest, retrieval, generation, guardrails, eval, observability, scaling, deployment, API reference, config reference) + 3 appendices (repo layout, troubleshooting, glossary)
- [x] Run script; verify 42 pages, ~378 KB; clickable PDF outline matches printed TOC; render sample pages to PNG and confirm layout
- [x] Replace Unicode box-drawing chars and arrows with ASCII in the two diagrams + the repo tree (Helvetica/Courier base14 fonts ship no box-drawing glyphs)
- [x] Link the PDF + a Book badge in the README

## Review

- verification run: `python scripts/generate_book.py` → `docs/documind-book.pdf` (42 pages, 378 KB, 87 outline entries: 15 top-level + 72 sections)
- behavior diff notes: book is byte-reproducible — uses `SOURCE_DATE_EPOCH` (default 1704067200) for both the matplotlib PNG timestamps in the sample report *and* this PDF's CreationDate/ModDate; same script run twice gives identical bytes
- residual risks: very long key strings in `kv_table` can wrap awkwardly on the inline code column (cosmetic); appendix bookmarks are clamped to outline level 1 because PyMuPDF rejects level 0

