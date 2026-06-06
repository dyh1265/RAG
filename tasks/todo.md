# Fix: tenant isolation for re-ingest + doc-scoped retrieval

## Plan
- [x] index_chunks(): pass tenant_id to store.delete_doc (was deleting across tenants for shared YouTube doc_ids)
- [x] Thread tenant+doc filter into retriever helper scrolls (hybrid, labeled figures/tables/algorithms, slide-scoped)
- [x] Tenant-scope expand_split_list_items scroll (optional filters kwarg)
- [x] Tests: tenant-scoped delete + tenant-filtered slide-scoped scroll
- [x] Run full suite

## Review
### Verification
- tests/core/test_index_chunks.py + tests/retrieval — 41 passed
- Full non-integration suite — 183 passed, 0 failures
### Behavior diff
- Re-ingesting a YouTube video as tenant A no longer wipes tenant B's copy (deterministic doc_id collision)
- Labeled-asset, slide-scoped, hybrid, and list-expand scrolls now carry tenant_id from request.filters; previously doc_id-only filters could read another tenant's chunks on doc_id collision
### Residual risks
- expand_split_list_items keeps a doc_id-only fallback for direct/test callers; production path always passes scoped filters
- Relies on request.filters carrying tenant_id (set by the query route)

---

# Feature: slide/page-scoped questions for YouTube lectures

## Plan
- [x] parse_page_reference() for "page N" / "slide N" (asset_refs.py)
- [x] _fetch_slide_scoped_chunks(): slide N content + transcript in its on-screen window
- [x] Wire into retrieve() (doc-scoped, no asset ref), prepend as priority hits
- [x] Tests (parser + retrieval window + non-video fallback)
- [x] Verify on real lecture in Docker

## Review
### Verification
- tests/retrieval: 31 passed (incl. new test_slide_scoped_retrieval.py)
- Live retrieve() "slide 7" on lecture c76bf0f4951aaf7c → slide 7 + transcript 315s-454s prepended (score 100)
### Behavior diff
- "what did the author say about slide 7" now returns slide 7's text + what was spoken while it showed, instead of generic semantic hits
- Non-video docs: returns [] (no slide timestamps) → unchanged semantic behavior
### Residual risks
- Page scoping only for video docs; PDF "page N" still semantic (intentional)
- Window = next-slide timestamp; rapid slide flips may merge brief slides

---

# Fix: YouTube document preview

## Plan

- [x] Resolve `slides.pdf` for `youtube:{video_id}` sources in admin file endpoint
- [x] Frontend: HEAD check + friendly message when no slide PDF
- [x] Tests for preview resolver + admin endpoint
- [x] Run tests + verify in Docker for ingested lecture

## Review

### Verification
- `pytest tests/video/test_preview.py tests/api/test_api.py::test_document_file_youtube_slides_pdf` — 5 passed
- Docker: `slides.pdf` at `data/processed/youtube/KAlcMLHBXNQ/`; resolver returns path for `youtube:KAlcMLHBXNQ`
- `HEAD /admin/documents/{id}/file` enabled (was 405)

### Behavior diff
- YouTube docs with slide extraction now preview `data/processed/youtube/{id}/slides.pdf`
- Transcript-only YouTube docs show explanatory message instead of raw JSON error

### Residual risks
- HEAD on preview URL may not work if nginx strips it; iframe fallback still possible
