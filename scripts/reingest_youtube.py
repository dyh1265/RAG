"""One-off: re-ingest a YouTube video under a specific tenant with the configured transcriber.

Usage (inside container):
    python /app/scripts/reingest_youtube.py <video_url> <tenant_id>
"""

from __future__ import annotations

import sys

from backend.core.config import get_settings
from backend.core.pipeline import PipelineConfig, RAGPipeline
from backend.video.youtube_ingestor import YouTubeIngestor


def main() -> None:
    url = sys.argv[1]
    tenant_id = sys.argv[2] if len(sys.argv) > 2 else "public"

    settings = get_settings()
    print(f"transcriber_provider={settings.transcriber_provider}", flush=True)

    config = PipelineConfig(
        use_hybrid=settings.use_hybrid,
        use_parent_expand=settings.use_parent_expand,
    )
    pipeline = RAGPipeline(config)
    ingestor = YouTubeIngestor(pipeline, settings)

    def on_progress(stage: str, message: str, detail=None) -> None:
        print(f"[{stage}] {message}", flush=True)

    result = ingestor.ingest(
        url,
        tenant_id=tenant_id,
        include_transcript=True,
        include_slides=True,
        on_progress=on_progress,
    )
    print(
        f"DONE chunk_count={result.ingest.chunk_count} "
        f"by_type={result.ingest.chunks_by_type}",
        flush=True,
    )


if __name__ == "__main__":
    main()
