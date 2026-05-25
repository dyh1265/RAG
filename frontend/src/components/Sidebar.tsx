import type { IngestResponse, FolderLoadProgress, LlmProvider, RecentDocument } from "../types";
import { BulkIndexPanel } from "./BulkIndexPanel";
import { RecentDocuments } from "./RecentDocuments";

interface SidebarProps {
  apiBase: string;
  onApiBaseChange: (url: string) => void;
  provider: LlmProvider;
  onProviderChange: (p: LlmProvider) => void;
  onRefreshHealth: () => void;
  docId: string | null;
  activeDocName?: string;
  ingestInfo: IngestResponse | null;
  recentDocs: RecentDocument[];
  docsLoading: boolean;
  onSelectDocument: (doc: RecentDocument) => void;
  onRemoveRecent: (docId: string) => void;
  onClearDoc: () => void;
  onSelectLocalFolder: (files: File[], folderName?: string) => void;
  bulkIndexing: boolean;
  folderProgress: FolderLoadProgress | null;
  uploadDoneToken?: number;
  apiReady: boolean;
}

export function Sidebar({
  apiBase,
  onApiBaseChange,
  provider,
  onProviderChange,
  onRefreshHealth,
  docId,
  activeDocName,
  ingestInfo,
  recentDocs,
  docsLoading,
  onSelectDocument,
  onRemoveRecent,
  onClearDoc,
  onSelectLocalFolder,
  bulkIndexing,
  folderProgress,
  uploadDoneToken,
  apiReady,
}: SidebarProps) {
  const demoUi = import.meta.env.VITE_DEMO_UI === "true";

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="logo">📄</span>
        <span>DocuMind</span>
      </div>

      <RecentDocuments
        documents={recentDocs}
        activeDocId={docId}
        loading={docsLoading}
        onSelect={onSelectDocument}
        onRemove={onRemoveRecent}
        onUploadNew={onClearDoc}
      />

      <BulkIndexPanel
        onSelectLocalFolder={onSelectLocalFolder}
        indexing={bulkIndexing}
        folderProgress={folderProgress}
        uploadDoneToken={uploadDoneToken}
        disabled={!apiReady}
      />

      {!demoUi && (
        <section className="sidebar-section">
          <label className="field-label" htmlFor="api-url">
            API URL
          </label>
          <input
            id="api-url"
            className="field-input"
            type="url"
            value={apiBase}
            onChange={(e) => onApiBaseChange(e.target.value)}
            placeholder="http://localhost:8002"
          />
          <button type="button" className="btn btn-ghost btn-sm" onClick={onRefreshHealth}>
            Check connection
          </button>
        </section>
      )}

      <section className="sidebar-section">
        <label className="field-label" htmlFor="provider">
          LLM provider
        </label>
        <select
          id="provider"
          className="field-input"
          value={provider}
          onChange={(e) => onProviderChange(e.target.value as LlmProvider)}
        >
          <option value="openai">OpenAI</option>
          <option value="ollama">Ollama</option>
        </select>
      </section>

      {docId && (
        <section className="sidebar-section doc-panel">
          <h3>Active document</h3>
          {activeDocName && <p className="active-doc-name">{activeDocName}</p>}
          <code className="doc-id">{docId}</code>
          {ingestInfo && ingestInfo.chunk_count > 0 && (
            <ul className="chunk-stats">
              <li>{ingestInfo.chunk_count} chunks</li>
              {Object.entries(ingestInfo.chunks_by_type).map(([type, count]) => (
                <li key={type}>
                  {type}: {count}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {!demoUi && (
        <footer className="sidebar-footer">
          <p>PII redaction on queries</p>
        </footer>
      )}
    </aside>
  );
}
