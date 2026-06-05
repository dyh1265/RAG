# YouTube lecture RAG

DocuMind can ingest a **YouTube lecture URL** and build a searchable document from:

1. **Transcript** — audio is downloaded, transcribed (OpenAI Whisper by default), chunked with timestamps, and indexed as `ChunkType.TRANSCRIPT` in the existing `text_chunks` collection.
2. **Slides** — video frames are sampled, near-duplicates removed, assembled into `slides.pdf`, then parsed and OCR-indexed through the **same PDF pipeline** used for uploads.

Transcript and slide chunks share one `doc_id` (`youtube:{video_id}` hash) so chat retrieval spans both modalities.

## UI

On the home screen, choose **Add YouTube Lecture** (next to **Upload PDF**):

- Paste a `youtube.com/watch`, `youtu.be`, or `/shorts/` URL.
- Toggle **Include transcript** and **Extract slides**.
- Optional **Advanced** → sample interval (default 2 s between frames).

Progress streams over SSE (`progress` / `done` / `error`), same as PDF upload.

## Ask about a specific slide

When slide extraction is enabled, you can scope a question to a single slide:

> *What did the author say about slide 7?*

DocuMind detects the `slide N` / `page N` reference and returns:

1. **Slide N's on-screen text** (the OCR'd slide content), and
2. **The transcript spoken while slide N was visible** — bounded by `[slide N timestamp, slide N+1 timestamp)`.

This works because slide chunks store `metadata.timestamp` (when the slide appeared) and transcript chunks store `start_time` / `end_time`. The retriever joins them on time, tags the spoken chunks with `aligned_slide_number`, and the answer generator labels them `Spoken during slide N` so the LLM summarizes the narration for that slide instead of a generic semantic hit.

Notes:
- Slide-scoped queries return **only** that slide + its narration (no unrelated semantic results), keeping citations focused.
- If no narration was indexed for that slide's time window (e.g. a title card with no speech), the answer describes the on-screen text and says narration wasn't indexed for that segment.
- Scoping applies to **video** documents; for PDFs, `page N` stays a normal semantic query.

## Slide-PDF preview

YouTube documents store `source_path` as `youtube:{video_id}` (a virtual path, not a file). When slide extraction ran, the in-app document preview resolves to the generated `data/processed/youtube/{video_id}/slides.pdf`. Transcript-only lectures have no PDF, so the preview shows an explanatory message instead of an error — chat still works from the indexed transcript.

## API

```bash
curl -N -X POST http://localhost:8002/ingest/youtube/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <session-token>" \
  -d '{
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "include_transcript": true,
    "include_slides": true,
    "sample_every_seconds": 2.0
  }'
```

Response `done` payload extends `IngestResponseOut` with `video_id`, `title`, `slides_pdf_path`, and optional `warnings`.

## Architecture (no separate YouTube stack)

```text
YouTube URL
  → backend/video/youtube_ingestor.py
  → transcript: download audio → transcribe → segments_to_chunks → RAGPipeline.index_chunks
  → slides: download video → sample frames → phash dedup → slides.pdf → parse → index_chunks (clear_existing=false)
  → same Qdrant collections, embeddings, retrieval, and answer generation as PDFs
```

Key modules live under [`backend/video/`](https://github.com/dyh1265/DocuMind/tree/master/backend/video).

## Citations

YouTube-specific fields are stored in `chunk.metadata` and passed through to API citations:

| Modality | Metadata | UI label example |
|---|---|---|
| Transcript | `start_time`, `end_time`, `youtube_url` | `Transcript 8:12–8:55` (links to watch URL) |
| Slide | `slide_number`, `timestamp`, `youtube_url` | `Slide 6, extracted around 8:20` |

Slide hits with a generated PDF also expose `page_number` for in-app preview jumps.

## Configuration

| Env var | Default | What |
|---|---|---|
| `YOUTUBE_INGEST_ENABLED` | `true` | When `false`, `POST /ingest/youtube/stream` returns 503. |
| `TRANSCRIBER_PROVIDER` | `openai` | `openai` (needs `OPENAI_API_KEY`) or `mock` for tests. |
| `YOUTUBE_SAMPLE_EVERY_SECONDS` | `2.0` | Frame sampling interval for slide extraction. |

Docker also needs **ffmpeg**, **yt-dlp**, **opencv-python-headless**, and **imagehash** in the API image (see `docker/Dockerfile`).

## Limitations

- Only ingest videos you have the right to process. YouTube support is intended for personal knowledge management, authorized lectures, and content you own or are permitted to analyze.
- Slide deduplication uses perceptual hashing (MVP). Fast scene changes or animated slides may produce extra pages.
- Transcription quality and cost depend on the configured provider (`openai` Whisper API by default).
- Very long videos increase download, transcription, and indexing time; CPU-only hosts should expect multi-minute ingests.

## Local testing without OpenAI transcription

Set `TRANSCRIBER_PROVIDER=mock` in `.env` to exercise download → chunk → index with canned transcript text (useful in Docker smoke tests).

> **Pitfall:** `mock` returns the **same two hardcoded segments** (~28 s of "treatment heterogeneity" text) for *every* video, regardless of audio. If a lecture shows only 1–2 transcript chunks with unrelated content, it was almost certainly ingested under `mock`. Set `TRANSCRIBER_PROVIDER=openai`, recreate the API container (`docker compose up -d rag-api`), then re-ingest the URL to replace the mock transcript with real Whisper output. The doc keeps its `doc_id` (derived from the video id), so re-ingest overwrites the previous vectors.
