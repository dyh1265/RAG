import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { RagApiClient, loadApiBase, saveApiBase } from "./api/client";
import type { ChatMessage, FolderLoadProgress, IngestResponse, LlmProvider, RecentDocument } from "./types";
import { Sidebar } from "./components/Sidebar";
import { PdfUploader } from "./components/PdfUploader";
import { ChatPanel } from "./components/ChatPanel";
import { DocumentPreview } from "./components/DocumentPreview";
import { StatusBadge } from "./components/StatusBadge";
import {
  addRecentDocument,
  basenameFromPath,
  loadActiveDocId,
  loadRecentDocuments,
  mergeDocumentLists,
  removeRecentDocument,
  saveActiveDocId,
} from "./storage/recentDocs";
import { clearChat, loadChat, saveChat } from "./storage/chatStorage";

function uid(): string {
  return crypto.randomUUID();
}

export default function App() {
  const [apiBase, setApiBase] = useState(loadApiBase);
  const [provider, setProvider] = useState<LlmProvider>("openai");
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "error">("checking");
  const [docId, setDocId] = useState<string | null>(() => loadActiveDocId());
  const [ingestInfo, setIngestInfo] = useState<IngestResponse | null>(null);
  const [recentDocs, setRecentDocs] = useState<RecentDocument[]>(() => loadRecentDocuments());
  const [docsLoading, setDocsLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    const active = loadActiveDocId();
    return active ? loadChat(active) : [];
  });
  const [ingesting, setIngesting] = useState(false);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bulkIndexing, setBulkIndexing] = useState(false);
  const [folderProgress, setFolderProgress] = useState<FolderLoadProgress | null>(null);
  const [uploadDoneToken, setUploadDoneToken] = useState(0);
  const [previewPage, setPreviewPage] = useState<number | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);

  const client = useMemo(() => new RagApiClient(apiBase), [apiBase]);
  const abortRef = useRef<AbortController | null>(null);

  const refreshDocuments = useCallback(async () => {
    setDocsLoading(true);
    try {
      const indexed = await client.listDocuments();
      const merged = mergeDocumentLists(loadRecentDocuments(), indexed);
      setRecentDocs(merged);

      const active = loadActiveDocId();
      if (active && merged.some((d) => d.docId === active)) {
        setDocId(active);
      }
    } catch {
      setRecentDocs(loadRecentDocuments());
    } finally {
      setDocsLoading(false);
    }
  }, [client]);

  const checkHealth = useCallback(async () => {
    setApiStatus("checking");
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        await client.health();
        setApiStatus("ok");
        void refreshDocuments();
        void client.ready().catch(() => undefined);
        return;
      } catch {
        if (attempt < 2) {
          await new Promise((r) => setTimeout(r, 2000));
        }
      }
    }
    setApiStatus("error");
  }, [client, refreshDocuments]);

  useEffect(() => {
    void checkHealth();
  }, [apiBase]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!docId) return;
    saveChat(docId, messages);
  }, [docId, messages]);

  useEffect(() => {
    if (!docId || apiStatus !== "ok") {
      setSuggestions([]);
      setSuggestionsLoading(false);
      return;
    }

    const controller = new AbortController();
    setSuggestionsLoading(true);
    void client
      .getDocumentSuggestions(docId, controller.signal)
      .then((result) => {
        setSuggestions(result.questions);
      })
      .catch(() => {
        setSuggestions([
          "Give me a brief overview of this document.",
          "What are the main takeaways?",
          "What topics does this document cover?",
        ]);
      })
      .finally(() => {
        setSuggestionsLoading(false);
      });

    return () => controller.abort();
  }, [docId, apiStatus, client]);

  const handleApiBaseChange = (url: string) => {
    saveApiBase(url);
    setApiBase(url);
  };

  const selectDocument = (doc: RecentDocument) => {
    abortRef.current?.abort();
    setAsking(false);
    setDocId(doc.docId);
    saveActiveDocId(doc.docId);
    setIngestInfo({
      doc_id: doc.docId,
      source_path: "",
      chunk_count: doc.chunkCount,
      chunks_by_type: {},
      vectors_by_collection: {},
      errors: [],
      skipped: false,
    });
    setMessages(loadChat(doc.docId));
    setError(null);
    setPreviewPage(null);
  };

  const handleIngest = async (file: File) => {
    setError(null);
    setIngesting(true);
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const result = await client.ingest(file, controller.signal);
      setDocId(result.doc_id);
      saveActiveDocId(result.doc_id);
      setIngestInfo(result);
      setMessages(loadChat(result.doc_id));
      const updated = addRecentDocument({
        docId: result.doc_id,
        name: file.name || basenameFromPath(result.source_path, result.doc_id),
        chunkCount: result.chunk_count,
        sourcePath: result.source_path || undefined,
      });
      setRecentDocs(mergeDocumentLists(updated, []));
      void refreshDocuments();
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setError((e as Error).message);
      }
    } finally {
      setIngesting(false);
    }
  };

  const handleAsk = async (query: string) => {
    if (!docId) return;
    setError(null);
    setAsking(true);

    const userMsg: ChatMessage = { id: uid(), role: "user", content: query };
    const pendingId = uid();
    setMessages((prev) => [
      ...prev,
      userMsg,
      { id: pendingId, role: "assistant", content: "", loading: true },
    ]);

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await client.query(
        { query, doc_id: docId, provider },
        controller.signal,
      );
      const conformity = response.metadata?.conformity;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? {
                id: pendingId,
                role: "assistant",
                content: response.answer || "_(no answer)_",
                citations: response.citations,
                conformityReason: conformity?.flagged
                  ? conformity.reason ?? "Taxonomy violation"
                  : undefined,
                latencyMs: response.latency_ms ?? undefined,
                piiRedacted: response.pii_redacted,
              }
            : m,
        ),
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        const msg = (e as Error).message;
        setError(msg);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === pendingId
              ? { id: pendingId, role: "assistant", content: `Error: ${msg}` }
              : m,
          ),
        );
      } else {
        setMessages((prev) => prev.filter((m) => m.id !== pendingId));
      }
    } finally {
      setAsking(false);
    }
  };

  const handleClearChat = () => {
    if (!docId) return;
    abortRef.current?.abort();
    clearChat(docId);
    setMessages([]);
    setAsking(false);
    setError(null);
  };

  const handleClearDoc = () => {
    setDocId(null);
    saveActiveDocId(null);
    setIngestInfo(null);
    setMessages([]);
    setError(null);
  };

  const handleRemoveRecent = async (id: string) => {
    setError(null);
    if (docId === id) {
      handleClearDoc();
    }
    clearChat(id);
    removeRecentDocument(id);
    setRecentDocs((prev) => prev.filter((d) => d.docId !== id));
    try {
      await client.deleteDocument(id);
      await refreshDocuments();
    } catch (e) {
      setError(`Could not delete document: ${(e as Error).message}`);
      await refreshDocuments();
    }
  };

  const handleLocalFolderSelect = async (files: File[], folderName?: string) => {
    setError(null);
    setBulkIndexing(true);
    const label = folderName ?? "folder";
    setFolderProgress({
      status: "running",
      source: "local",
      folderName,
      total: files.length,
      processed: 0,
      ingested: 0,
      skipped: 0,
      failed: 0,
      currentFile: "Starting bulk job…",
    });
    try {
      const { job_id: jobId } = await client.bulkIngestStart(label, files.length);

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        setFolderProgress((prev) =>
          prev
            ? {
                ...prev,
                currentFile: file.name,
                processed: i,
                message: `Uploading ${i + 1}/${files.length}…`,
              }
            : prev,
        );
        await client.bulkIngestUploadFile(jobId, file);
        setFolderProgress((prev) =>
          prev
            ? {
                ...prev,
                processed: i + 1,
                currentFile: file.name,
                message: `Uploaded ${i + 1}/${files.length} — queue next`,
              }
            : prev,
        );
      }

      setFolderProgress((prev) =>
        prev
          ? { ...prev, currentFile: "Queueing Celery tasks…", message: "Redis + worker" }
          : prev,
      );
      await client.bulkIngestRun(jobId);

      let job = await client.getBulkIngestJob(jobId);
      let lastProcessed = job.processed;
      let stallPolls = 0;
      let resumeAttempted = false;
      while (job.status === "uploading" || job.status === "queued" || job.status === "running") {
        setFolderProgress({
          status: "running",
          source: "local",
          folderName,
          total: job.total,
          processed: job.processed,
          ingested: job.ingested,
          skipped: job.skipped,
          failed: job.failed,
          currentFile: job.current_file ?? undefined,
          message:
            job.status === "queued"
              ? "Queued on Celery…"
              : `Indexing ${job.processed}/${job.total} (Redis cache)`,
        });
        await new Promise((r) => setTimeout(r, 1500));
        job = await client.getBulkIngestJob(jobId);

        if (job.processed === lastProcessed && job.status === "running" && job.processed < job.total) {
          stallPolls += 1;
        } else {
          stallPolls = 0;
          lastProcessed = job.processed;
        }
        if (!resumeAttempted && stallPolls >= 12 && job.processed < job.total) {
          resumeAttempted = true;
          try {
            const { queued } = await client.bulkIngestResume(jobId);
            if (queued > 0) {
              stallPolls = 0;
            }
          } catch {
            /* worker may still be busy; keep polling */
          }
        }
      }

      void refreshDocuments();
      setFolderProgress({
        status: job.status === "error" ? "error" : "done",
        source: "local",
        folderName,
        total: job.total,
        processed: job.processed,
        ingested: job.ingested,
        skipped: job.skipped,
        failed: job.failed,
        message:
          job.message ??
          `${job.ingested} ingested · ${job.skipped} skipped · ${job.failed} failed`,
      });
      if (job.status === "error") {
        setError(job.message ?? "Bulk ingest failed");
      }
    } catch (e) {
      const err = (e as Error).message;
      setError(err);
      setFolderProgress((prev) =>
        prev
          ? { ...prev, status: "error", message: err }
          : {
              status: "error",
              source: "local",
              folderName,
              total: files.length,
              processed: 0,
              ingested: 0,
              skipped: 0,
              failed: 0,
              message: err,
            },
      );
    } finally {
      setBulkIndexing(false);
      setUploadDoneToken((t) => t + 1);
    }
  };

  const activeDoc = recentDocs.find((d) => d.docId === docId);

  return (
    <div className="app">
      <Sidebar
        apiBase={apiBase}
        onApiBaseChange={handleApiBaseChange}
        provider={provider}
        onProviderChange={setProvider}
        onRefreshHealth={checkHealth}
        docId={docId}
        activeDocName={activeDoc?.name}
        ingestInfo={ingestInfo}
        recentDocs={recentDocs}
        docsLoading={docsLoading}
        onSelectDocument={selectDocument}
        onRemoveRecent={handleRemoveRecent}
        onClearDoc={handleClearDoc}
        onSelectLocalFolder={handleLocalFolderSelect}
        bulkIndexing={bulkIndexing}
        folderProgress={folderProgress}
        uploadDoneToken={uploadDoneToken}
        apiReady={apiStatus === "ok"}
      />

      <main className="main">
        <header className="header">
          <div>
            <h1>DocuMind</h1>
            <p className="subtitle">Multimodal RAG with taxonomy conformity</p>
          </div>
          <StatusBadge status={apiStatus} apiBase={apiBase} />
        </header>

        {error && (
          <div className="banner banner-error" role="alert">
            {error}
          </div>
        )}

        {!docId ? (
          <PdfUploader onUpload={handleIngest} ingesting={ingesting} />
        ) : (
          <div className="workspace">
            <DocumentPreview
              docId={docId}
              docName={activeDoc?.name}
              apiBase={apiBase}
              page={previewPage}
            />
            <ChatPanel
              messages={messages}
              onSend={handleAsk}
              onClearChat={handleClearChat}
              onCitationPage={setPreviewPage}
              disabled={asking || apiStatus !== "ok"}
              docId={docId}
              docName={activeDoc?.name}
              suggestions={suggestions}
              suggestionsLoading={suggestionsLoading}
            />
          </div>
        )}
      </main>
    </div>
  );
}
