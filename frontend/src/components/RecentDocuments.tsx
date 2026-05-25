import type { RecentDocument } from "../types";

interface RecentDocumentsProps {
  documents: RecentDocument[];
  activeDocId: string | null;
  loading: boolean;
  onSelect: (doc: RecentDocument) => void;
  onRemove: (docId: string) => void | Promise<void>;
  onUploadNew: () => void;
}

function formatWhen(iso: string): string {
  if (!iso) return "indexed";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "indexed";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function RecentDocuments({
  documents,
  activeDocId,
  loading,
  onSelect,
  onRemove,
  onUploadNew,
}: RecentDocumentsProps) {
  return (
    <section className="sidebar-section recent-docs">
      <div className="recent-docs-header">
        <h3>Recent documents</h3>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onUploadNew}>
          + New
        </button>
      </div>

      {loading && documents.length === 0 && (
        <p className="recent-empty">Loading…</p>
      )}

      {!loading && documents.length === 0 && (
        <p className="recent-empty">Upload a PDF to get started.</p>
      )}

      <ul className="recent-list">
        {documents.map((doc) => {
          const active = doc.docId === activeDocId;
          return (
            <li key={doc.docId} className={active ? "recent-item active" : "recent-item"}>
              <button
                type="button"
                className="recent-select"
                onClick={() => onSelect(doc)}
                title={doc.docId}
              >
                <span className="recent-name">{doc.name}</span>
                <span className="recent-meta">
                  {doc.chunkCount} chunks · {formatWhen(doc.ingestedAt)}
                </span>
              </button>
              <button
                type="button"
                className="recent-remove"
                aria-label={`Delete ${doc.name}`}
                onClick={(e) => {
                  e.stopPropagation();
                  void onRemove(doc.docId);
                }}
              >
                ×
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
