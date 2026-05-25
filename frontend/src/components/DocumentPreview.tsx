import { useEffect, useState } from "react";
import { documentPreviewUrl } from "../api/client";

interface DocumentPreviewProps {
  docId: string;
  docName?: string;
  apiBase: string;
  page?: number | null;
}

export function DocumentPreview({ docId, docName, apiBase, page }: DocumentPreviewProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const baseUrl = documentPreviewUrl(apiBase, docId);
  const src = page && page > 0 ? `${baseUrl}#page=${page}` : baseUrl;

  useEffect(() => {
    setLoadError(null);
  }, [docId, page]);

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
          <a
            className="btn btn-sm doc-preview-btn doc-preview-open"
            href={baseUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open
          </a>
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
            <p className="doc-preview-error" role="alert">
              {loadError}
            </p>
          ) : (
            <iframe
              key={src}
              className="doc-preview-frame"
              src={src}
              title={docName ? `Preview: ${docName}` : `Preview document ${docId}`}
              onError={() => setLoadError("Could not load PDF preview.")}
            />
          )}
        </div>
      )}
    </section>
  );
}
