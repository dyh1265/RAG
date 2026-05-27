# Screenshots / GIFs

These images are referenced from the top-level [README](../../README.md#demo)
and are intentionally not generated — drop in your own captures so the repo
looks polished to recruiters and hiring managers.

## What to capture

| File | What it should show | Suggested size |
|---|---|---|
| `demo.gif` | End-to-end loop: upload PDF → ask question → cited answer appears. 6–12 s loop, ≤ 5 MB. | 1280×800 |
| `upload.png` | The bulk-index / single-upload panel mid-upload (progress bar visible). | 1280×800 |
| `chat.png` | The chat panel after a question, with an answer and inline citations. | 1280×800 |
| `citations.png` | The document preview / source panel showing the cited page or figure. | 1280×800 |

## How to capture quickly

1. Start the stack:
   ```bash
   cd docker
   docker compose --profile production up -d --build
   ```
2. Open http://localhost, upload [`data/raw/sample_report.pdf`](../../data/raw/sample_report.pdf).
3. Ask: *"What does Figure 3 show about revenue trends?"*
4. Use any screen recorder for the GIF (e.g. ScreenToGif on Windows,
   Kap on macOS, Peek on Linux) and crop to the browser viewport.

The README will gracefully render with broken-image icons until these files
exist; that is intentional so the placeholders are not silently forgotten.
