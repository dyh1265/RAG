import type { FolderLoadProgress } from "../types";

interface FolderLoadStatusBarProps {
  progress: FolderLoadProgress;
}

export function FolderLoadStatusBar({ progress }: FolderLoadStatusBarProps) {
  const { status, source, total, processed, ingested, skipped, failed, currentFile, message } =
    progress;

  // Already-indexed docs (fingerprint match) come back from the worker as
  // "skipped". For the user, those are still ready to query, so we surface
  // them as part of the indexed total instead of looking like a failure.
  const indexed = ingested + skipped;
  const hasTotal = total > 0;
  const pct = hasTotal
    ? Math.min(100, Math.round((Math.min(processed, total) / total) * 100))
    : null;
  const indeterminate = status === "running" && !hasTotal;
  const allFailed = status === "done" && indexed === 0 && failed > 0;

  const runningLabel = (): string => {
    if (source !== "local") return "Indexing server folder…";
    const m = message ?? "";
    if (m.includes("Uploaded") || m.includes("Uploading")) return "Uploading PDFs…";
    if (m.includes("Celery") || m.includes("Redis") || m.includes("Indexing")) {
      return "Indexing via Celery…";
    }
    return "Preparing bulk job…";
  };

  const label =
    status === "running"
      ? runningLabel()
      : status === "done"
        ? allFailed
          ? "No documents indexed"
          : failed > 0
            ? "Done — some files failed"
            : "Complete — ready to chat"
        : "Failed";

  const summary =
    status === "done"
      ? failed > 0
        ? `${indexed} of ${total} ready · ${failed} failed`
        : `${indexed} of ${total} ready to chat`
      : null;

  return (
    <div
      className={`folder-load-status status-${status}${allFailed ? " status-empty" : ""}`}
      role="status"
      aria-live="polite"
      aria-busy={status === "running"}
    >
      <div className="folder-load-header">
        <span className="folder-load-label">{label}</span>
        {hasTotal && (
          <span className="folder-load-count">
            {Math.min(processed, total)} / {total}
          </span>
        )}
      </div>

      <div className="folder-load-bar-track" aria-hidden="true">
        <div
          className={indeterminate ? "folder-load-bar indeterminate" : "folder-load-bar"}
          style={pct !== null ? { width: `${pct}%` } : undefined}
        />
      </div>

      {status === "running" && currentFile && (
        <p className="folder-load-current" title={currentFile}>
          {currentFile}
        </p>
      )}

      <div className="folder-load-stats">
        <span className="stat-ingested">
          {indexed} indexed
          {skipped > 0 && ingested > 0 && (
            <span className="stat-detail"> ({ingested} new · {skipped} already indexed)</span>
          )}
          {skipped > 0 && ingested === 0 && (
            <span className="stat-detail"> (already indexed)</span>
          )}
        </span>
        {failed > 0 && <span className="stat-failed">{failed} failed</span>}
      </div>

      {summary && <p className="folder-load-summary">{summary}</p>}
      {failed > 0 && status === "done" && (
        <p className="folder-load-hint">
          Failed files usually have no extractable text (scanned PDFs). Try uploading them one
          at a time so OCR runs.
        </p>
      )}
      {message && status === "running" && <p className="folder-load-message">{message}</p>}
    </div>
  );
}
