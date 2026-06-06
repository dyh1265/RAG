# Screenshots / GIFs

These images are referenced from the top-level [README](../../README.md#demo).
They are generated **programmatically** by driving the live UI with Playwright
(via the bundled Cursor `browse` plugin) and assembling frames with Pillow — so
they can be regenerated deterministically after UI changes.

## Files

| File | What it shows | Size |
|---|---|---|
| `demo.gif` | PDF loop: upload → ask → cited answer. | 1280×800, ≤ 5 MB |
| `upload.png` / `chat.png` / `citations.png` | Static PDF stills (upload, cited answer, source page). | 1280×800 |
| `demo_youtube_ingest.gif` | YouTube ingest progress (transcribe audio, sample frames, index slides). | 1280×800, ≤ 5 MB |
| `demo_youtube_qa.gif` | Slide-scoped Q&A: *"What did the author say about slide 7?"* → answer citing the slide + transcript timestamps. | 1280×800, ≤ 5 MB |

## Regenerate

Start the stack and keep `TRANSCRIBER_PROVIDER=openai` (real transcripts):

```bash
cd docker
docker compose --profile production up -d --build
```

PDF demo (upload [`data/raw/sample_report.pdf`](../../data/raw/sample_report.pdf), asks about Figure 3):

```bash
node scripts/capture_readme_demo.mjs    # frames -> docs/images/demo_frames/
node scripts/export_readme_images.mjs   # upload.png / chat.png / citations.png
python scripts/assemble_demo_gif.py     # -> docs/images/demo.gif
```

YouTube demo (ingests a lecture, then asks a slide-scoped question):

```bash
node scripts/capture_youtube_demo.mjs       # frames -> docs/images/yt_frames/{ingest,qa}/
python scripts/assemble_youtube_gifs.py     # -> demo_youtube_ingest.gif + demo_youtube_qa.gif
```

Override the video or question via env vars: `DEMO_YT_URL`, `DEMO_YT_QUERY`.
The capture runs headless as the `public` tenant, so it ingests fresh in-session
before querying (no dependency on previously indexed documents).
