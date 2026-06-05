import { useEffect, useState } from "react";
import { documentPreviewUrl } from "../api/client";

interface DocumentPreviewProps {
  docId: string;
  docName?: string;
  sourcePath?: string;
  apiBase: string;
  page?: number | null;
}

function isYouTubeSource(sourcePath?: string): boolean {
  return Boolean(sourcePath?.startsWith("youtube:"));
}

export function DocumentPreview({
  docId,
  docName,
  sourcePath,
  apiBase,
  page,
}: DocumentPreviewProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [previewReady, setPreviewReady] = useState(false);

  const baseUrl = documentPreviewUrl(apiBase, docId);
  const src = page && page > 0 ? `${baseUrl}#page=${page}` : baseUrl;
  const youtubeDoc = isYouTubeSource(sourcePath);

  useEffect(() => {
    setLoadError(null);
    setPreviewReady(false);

    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(baseUrl, { method: "HEAD" });
        if (cancelled) return;
        const contentType = res.headers.get("content-type") ?? "";
        if (res.ok && contentType.includes("application/pdf")) {
          setPreviewReady(true);
          return;
        }
        setLoadError(
          youtubeDoc
            ? "No slide PDF is available for this lecture. Chat still works using the indexed transcript."
            : "Could not load PDF preview.",
        );
      } catch {
        if (!cancelled) {
          setLoadError(
            youtubeDoc
              ? "No slide PDF is available for this lecture. Chat still works using the indexed transcript."
              : "Could not load PDF preview.",
          );
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [baseUrl, docId, page, youtubeDoc]);

  return (
    <section className={`doc-preview${collapsed ? " doc-preview-collapsed" : ""}`}>
      <div className="doc-preview-header">
        <div className="doc-preview-title">
          <span className="doc-preview-label">Preview</span>
          {docName && <span className="doc-preview-name">{docName}</span>}
        </div>
        <div className="doc-preview-actions">
          {page && page > 0 && (
            <span className="doc-preview-page">Page {page}</span>
          )}
          {previewReady && (
            <a
              className="btn btn-sm doc-preview-btn doc-preview-open"
              href={baseUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open
            </a>
          )}
          <button
            type="button"
            className="btn btn-sm doc-preview-btn"
            onClick={() => setCollapsed((v) => !v)}
            aria-expanded={!collapsed}
          >
            {collapsed ? "Show" : "Hide"}
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className="doc-preview-frame-wrap">
          {loadError ? (
            <p className="doc-preview-error" role="status">
              {loadError}
            </p>
          ) : previewReady ? (
            <iframe
              key={src}
              className="doc-preview-frame"
              src={src}
              title={docName ? `Preview: ${docName}` : `Preview document ${docId}`}
            />
          ) : (
            <p className="doc-preview-loading">Loading preview…</p>
          )}
        </div>
      )}
    </section>
  );
}
