import { useEffect, useRef, useState } from "react";
import type { IngestProgressEvent, YouTubeIngestOptions } from "../types";

interface YouTubeIngestCardProps {
  onIngest: (url: string, options: YouTubeIngestOptions) => void;
  ingesting: boolean;
  ingestLabel?: string | null;
  ingestProgress?: IngestProgressEvent | null;
}

const STAGE_UI: Record<string, { label: string; hint: string }> = {
  validating: { label: "Validating", hint: "Checking YouTube URL" },
  downloading_audio: { label: "Downloading audio", hint: "Fetching audio track via yt-dlp" },
  transcribing: { label: "Transcribing", hint: "Converting speech to timestamped text" },
  chunking_transcript: { label: "Chunking transcript", hint: "Grouping segments for retrieval" },
  indexing_transcript: { label: "Indexing transcript", hint: "Embedding and storing in Qdrant" },
  downloading_video: { label: "Downloading video", hint: "Fetching video for slide extraction" },
  sampling_frames: { label: "Sampling frames", hint: "Extracting frames at fixed intervals" },
  detecting_slides: { label: "Detecting slides", hint: "Removing near-duplicate frames" },
  building_pdf: { label: "Building PDF", hint: "Assembling unique slides into slides.pdf" },
  indexing_slides: { label: "Indexing slides", hint: "OCR and indexing slide content" },
  enriching: { label: "Enriching", hint: "Chunking and contextual enrichment" },
  redacting: { label: "PII redaction", hint: "Scanning chunk text for sensitive patterns" },
  embedding: { label: "Embedding", hint: "BGE-M3 + CLIP vectors" },
  indexing: { label: "Indexing", hint: "Writing vectors to Qdrant" },
};

function formatDuration(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

function detailLine(progress: IngestProgressEvent | null | undefined): string | null {
  if (!progress?.detail) return null;
  const d = progress.detail;
  if (typeof d.chunk_count === "number") {
    return `${d.chunk_count} chunks`;
  }
  if (typeof d.vector_count === "number") {
    return `${d.vector_count} vectors`;
  }
  if (d.vectors_by_collection && typeof d.vectors_by_collection === "object") {
    const parts = Object.entries(d.vectors_by_collection as Record<string, number>).map(
      ([k, v]) => `${k}: ${v}`,
    );
    if (parts.length) return parts.join(" · ");
  }
  return null;
}

export function YouTubeIngestCard({
  onIngest,
  ingesting,
  ingestLabel,
  ingestProgress,
}: YouTubeIngestCardProps) {
  const [url, setUrl] = useState("");
  const [includeTranscript, setIncludeTranscript] = useState(true);
  const [includeSlides, setIncludeSlides] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [sampleEverySeconds, setSampleEverySeconds] = useState(2.0);
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    if (!ingesting) {
      startRef.current = null;
      setElapsed(0);
      return;
    }
    startRef.current = performance.now();
    setElapsed(0);
    const id = window.setInterval(() => {
      if (startRef.current != null) {
        setElapsed((performance.now() - startRef.current) / 1000);
      }
    }, 500);
    return () => window.clearInterval(id);
  }, [ingesting]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed || ingesting) return;
    onIngest(trimmed, {
      includeTranscript,
      includeSlides,
      sampleEverySeconds,
    });
  };

  const stageKey = ingestProgress?.stage ?? "validating";
  const ui = STAGE_UI[stageKey] ?? {
    label: stageKey,
    hint: ingestProgress?.message ?? "Processing…",
  };
  const extra = detailLine(ingestProgress);

  return (
    <div className="upload-zone">
      <div className={`drop-area youtube-ingest ${ingesting ? "drop-area-busy" : ""}`}>
        {ingesting ? (
          <>
            <div className="spinner" aria-hidden />
            <p className="drop-title">{ui.label}…</p>
            <p className="hint">{ingestProgress?.message ?? ui.hint}</p>
            {extra && <p className="ingest-detail">{extra}</p>}
            {ingestLabel && (
              <p className="ingest-meta">
                <span className="ingest-meta-file" title={ingestLabel}>
                  {ingestLabel}
                </span>
                <span className="ingest-meta-dot">·</span>
                <span className="ingest-meta-elapsed">{formatDuration(elapsed)} elapsed</span>
              </p>
            )}
          </>
        ) : (
          <form className="youtube-form" onSubmit={handleSubmit}>
            <div className="drop-icon">▶</div>
            <p className="drop-title">Add a YouTube lecture</p>
            <p className="hint">Paste a watch, youtu.be, or shorts URL</p>
            <input
              type="url"
              className="youtube-url-input"
              placeholder="https://www.youtube.com/watch?v=…"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={ingesting}
              required
            />
            <div className="youtube-options">
              <label className="youtube-check">
                <input
                  type="checkbox"
                  checked={includeTranscript}
                  onChange={(e) => setIncludeTranscript(e.target.checked)}
                />
                Include transcript
              </label>
              <label className="youtube-check">
                <input
                  type="checkbox"
                  checked={includeSlides}
                  onChange={(e) => setIncludeSlides(e.target.checked)}
                />
                Extract slides
              </label>
            </div>
            <button
              type="button"
              className="btn btn-ghost youtube-advanced-toggle"
              onClick={() => setShowAdvanced((v) => !v)}
            >
              {showAdvanced ? "Hide advanced" : "Advanced options"}
            </button>
            {showAdvanced && (
              <label className="youtube-advanced">
                Sample every{" "}
                <input
                  type="number"
                  min={0.5}
                  max={30}
                  step={0.5}
                  value={sampleEverySeconds}
                  onChange={(e) => setSampleEverySeconds(Number(e.target.value))}
                />{" "}
                seconds
              </label>
            )}
            <button
              type="submit"
              className="btn btn-primary"
              disabled={!url.trim() || (!includeTranscript && !includeSlides)}
            >
              Ingest video
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
