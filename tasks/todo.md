# Task: YouTube lecture RAG demo media for README

Goal: Add demo GIFs for the YouTube-lecture RAG flow (ingest progress + slide-scoped
Q&A), generated programmatically by driving the live UI, and reference them in the
README and the capture doc.

## Plan

- [x] Write `scripts/capture_youtube_demo.mjs` (Playwright): YouTube tab → paste URL →
      capture distinct ingest stages → slide-scoped question → cited answer →
      expand citations / jump to slide page.
- [x] Add `scripts/assemble_youtube_gifs.py` (Pillow): build
      `demo_youtube_ingest.gif` + `demo_youtube_qa.gif` (1280×800, ≤ 5 MB).
- [x] Run capture against the live stack (Gemma lecture, "slide 7" question).
- [x] Reference both GIFs in `README.md` under **YouTube lecture RAG**.
- [x] Update `docs/images/README.md` to document the automated capture/regenerate flow.

## Review

- **Verification run:** Stack healthy (frontend 200, `/api/health` ok,
  `TRANSCRIBER_PROVIDER=openai`, `YOUTUBE_INGEST_ENABLED=true`). Capture script
  exited 0 in ~100 s. Captured 10 ingest frames (7 distinct stages incl.
  "Sampling frames…", "Indexing slides…") + 4 Q&A frames. Assembler emitted
  `demo_youtube_ingest.gif` (236.6 KB) and `demo_youtube_qa.gif` (219.3 KB),
  both well under the 5 MB budget.
- **Behavior diff:** README's YouTube section now shows the ingest-progress GIF
  and a slide-scoped Q&A GIF whose answer cites **Slide 7 (extracted ~2:32)** and
  **Transcript 2:14–3:27** with the sidebar chunk breakdown (transcript/figure/
  page_image). docs/images/README.md now documents programmatic regeneration
  instead of "drop in your own captures".
- **Residual risks:** (1) Slide-preview frame's PDF canvas renders blank (lazy
  PDF.js load); the expanded-citations content is the key signal so this is
  cosmetic. (2) Capture runs as the `public` tenant and re-ingests in-session, so
  it depends on a live OpenAI key + reachable YouTube; flaky network would fail
  the run (script raises after a 15-min ingest deadline). (3) Unrelated working-
  tree changes (`answer_generator.py`, `generate_book.py`, `tsconfig.tsbuildinfo`)
  are intentionally left out of any demo commit.

---

# Task: Add YouTube info to the generated book

Goal: Document DocuMind's YouTube-lecture ingestion in the long-form reference
book produced by `scripts/generate_book.py`, faithful to the code
(`backend/video/`, `backend/api/routers/youtube.py`, `backend/core/config.py`)
and the wiki (`docs/wiki/YouTube-Lecture-RAG.md`).

## Plan

- [x] Add a new **Chapter 13 — Ingesting YouTube Lectures** before Appendix A.
      Placed at the end on purpose so existing in-prose "Chapter N" references
      (5, 6, 10, 11, 12) and the Chapter 1-12 grouping stay valid.
- [x] Add a forward reference from Chapter 3 (Ingestion) and update the Preface
      "How to read it" section.
- [x] Add `POST /ingest/youtube/stream` to the Chapter 11 API reference.
- [x] Add a "YouTube lecture ingest" block to the Chapter 12 config reference.
- [x] Update Appendix A repo layout (`backend/video/`, routers list) and
      Appendix C glossary (Transcript chunk, Slide alignment).
- [x] Regenerate the PDF and verify.

## Review

- **Verification run:** `python scripts/generate_book.py` exits 0 →
  `docs/documind-book.pdf`, now 45 pages (was 41). Inspected with PyMuPDF:
  TOC still fits its 3 reserved pages (Contents pages 3-5, Chapter 1 page 6) so
  no stray appended TOC page and page numbers stay correct; `CHAPTER 13 —
  Ingesting YouTube Lectures` renders on page 37 with all sections; Chapter 12
  "YouTube lecture ingest" block on page 35; Appendix A shifted to page 40;
  outline has 95 entries including the new chapter. No linter errors.
- **Behavior diff:** Book now covers YouTube ingestion end-to-end (two
  modalities, ingest path, slide-scoped Q&A, citations/preview, operating it,
  limitations), plus the endpoint, config keys, repo-layout, and glossary terms.
- **Residual risks:** PDF is byte-reproducible via SOURCE_DATE_EPOCH; commit the
  regenerated `docs/documind-book.pdf` with the script change. Content mirrors
  the wiki/code as of this change; regenerate if those drift.
