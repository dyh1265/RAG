import { useEffect, useRef, useState } from "react";
import type { IngestProgressEvent } from "../types";

interface PdfUploaderProps {
  onUpload: (file: File) => void;
  ingesting: boolean;
  ingestFile?: { name: string; size: number } | null;
  ingestProgress?: IngestProgressEvent | null;
}

const STAGE_UI: Record<string, { label: string; hint: string }> = {
  uploading: {
    label: "Uploading",
    hint: "Saving PDF on the server",
  },
  parsing: {
    label: "Parsing PDF",
    hint: "Extracting text, tables, and figures from pages",
  },
  enriching: {
    label: "Chunking & enriching",
    hint: "Splitting into chunks and attaching section paths",
  },
  redacting: {
    label: "PII redaction",
    hint: "Scanning chunk text for sensitive patterns",
  },
  embedding: {
    label: "Embedding",
    hint: "BGE-M3 (text) + CLIP (figures) on GPU/CPU",
  },
  indexing: {
    label: "Indexing",
    hint: "Writing vectors to Qdrant collections",
  },
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

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

export function PdfUploader({
  onUpload,
  ingesting,
  ingestFile,
  ingestProgress,
}: PdfUploaderProps) {
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

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUpload(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file?.type === "application/pdf") onUpload(file);
  };

  const stageKey = ingestProgress?.stage ?? "parsing";
  const ui = STAGE_UI[stageKey] ?? {
    label: stageKey,
    hint: ingestProgress?.message ?? "Processing…",
  };
  const extra = detailLine(ingestProgress);

  return (
    <div className="upload-zone">
      <div
        className={`drop-area ${ingesting ? "drop-area-busy" : ""}`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
      >
        {ingesting ? (
          <>
            <div className="spinner" aria-hidden />
            <p className="drop-title">{ui.label}…</p>
            <p className="hint">{ingestProgress?.message ?? ui.hint}</p>
            {extra && <p className="ingest-detail">{extra}</p>}
            {ingestFile && (
              <p className="ingest-meta">
                <span className="ingest-meta-file" title={ingestFile.name}>
                  {ingestFile.name}
                </span>
                <span className="ingest-meta-dot">·</span>
                <span>{formatBytes(ingestFile.size)}</span>
                <span className="ingest-meta-dot">·</span>
                <span className="ingest-meta-elapsed">{formatDuration(elapsed)} elapsed</span>
              </p>
            )}
          </>
        ) : (
          <>
            <div className="drop-icon">↑</div>
            <p className="drop-title">Upload a PDF to get started</p>
            <p className="hint">Drag and drop or choose a file</p>
            <label className="btn btn-primary">
              Choose PDF
              <input
                type="file"
                accept="application/pdf"
                hidden
                onChange={handleChange}
              />
            </label>
          </>
        )}
      </div>
    </div>
  );
}
