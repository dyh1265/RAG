import type { FolderLoadProgress } from "../types";

interface FolderLoadStatusBarProps {
  progress: FolderLoadProgress;
}

export function FolderLoadStatusBar({ progress }: FolderLoadStatusBarProps) {
  const { status, source, total, processed, ingested, skipped, failed, currentFile, message } =
    progress;

  const hasTotal = total > 0;
  const pct = hasTotal
    ? Math.min(100, Math.round((Math.min(processed, total) / total) * 100))
    : null;
  const indeterminate = status === "running" && !hasTotal;

  const label =
    status === "running"
      ? source === "local"
        ? message?.includes("Celery") ||
          message?.includes("Redis") ||
          message?.includes("Indexing") ||
          message?.includes("Uploaded")
          ? message?.includes("Uploaded")
            ? "Uploading PDFs…"
            : "Indexing via Celery…"
          : "Preparing bulk job…"
        : "Indexing server folder…"
      : status === "done"
        ? "Complete"
        : "Failed";

  return (
    <div
      className={`folder-load-status status-${status}`}
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
        <span className="stat-ingested">{ingested} ingested</span>
        {skipped > 0 && <span className="stat-skipped">{skipped} skipped</span>}
        {failed > 0 && <span className="stat-failed">{failed} failed</span>}
      </div>

      {message && <p className="folder-load-message">{message}</p>}
    </div>
  );
}
