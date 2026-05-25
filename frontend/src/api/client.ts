import type {
  BulkIngestJob,
  BulkIngestStartResponse,
  DirectoryBrowseResponse,
  DocumentSummary,
  DocumentSuggestions,
  DirectoryIngestResponse,
  HealthResponse,
  IngestResponse,
  LlmProvider,
  QueryResponse,
  ReadyResponse,
} from "../types";

const STORAGE_KEY = "documind.apiUrl";

/** Default: same-origin `/api` proxy (Vite dev + prod nginx). */
export function getDefaultApiBase(): string {
  const fromEnv = import.meta.env.VITE_RAG_API_URL as string | undefined;
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  return "/api";
}

export function loadApiBase(): string {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) {
    const normalized = stored.replace(/\/$/, "");
    // Prefer same-origin proxy on prod UI (5174) — cross-port fetch often fails in embedded browsers.
    if (normalized === "http://localhost:8002" && window.location.port === "5174") {
      return "/api";
    }
    return normalized;
  }
  return getDefaultApiBase();
}

function fetchWithTimeout(url: string, init: RequestInit = {}, ms = 15_000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  const { signal: userSignal, ...rest } = init;

  const onAbort = () => controller.abort();
  userSignal?.addEventListener("abort", onAbort, { once: true });

  return fetch(url, { ...rest, signal: controller.signal }).finally(() => {
    clearTimeout(timer);
    userSignal?.removeEventListener("abort", onAbort);
  });
}

export function saveApiBase(url: string): void {
  localStorage.setItem(STORAGE_KEY, url.replace(/\/$/, ""));
}

export function documentPreviewUrl(apiBase: string, docId: string): string {
  const base = apiBase.replace(/\/$/, "");
  return `${base}/admin/documents/${encodeURIComponent(docId)}/file`;
}

export class RagApiClient {
  constructor(private baseUrl: string) {}

  private static CONNECT_TIMEOUT_MS = 15_000;

  private url(path: string): string {
    return `${this.baseUrl.replace(/\/$/, "")}${path}`;
  }

  async health(signal?: AbortSignal): Promise<HealthResponse> {
    const res = await fetchWithTimeout(
      this.url("/health"),
      { signal },
      RagApiClient.CONNECT_TIMEOUT_MS,
    );
    if (!res.ok) throw new Error(`Health check failed (${res.status})`);
    return res.json();
  }

  async ready(signal?: AbortSignal): Promise<ReadyResponse> {
    const res = await fetchWithTimeout(
      this.url("/ready"),
      { signal },
      RagApiClient.CONNECT_TIMEOUT_MS,
    );
    const data = await res.json();
    if (!res.ok) throw new Error(data.status ?? "not ready");
    return data;
  }

  async ingest(file: File, signal?: AbortSignal): Promise<IngestResponse> {
    const form = new FormData();
    form.append("file", file, file.name);
    const res = await fetch(this.url("/ingest"), {
      method: "POST",
      body: form,
      signal,
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `Ingest failed (${res.status})`);
    }
    return res.json();
  }

  async bulkIngestStart(
    folderName: string,
    totalFiles: number,
    signal?: AbortSignal,
  ): Promise<BulkIngestStartResponse> {
    const res = await fetch(this.url("/ingest/bulk/start"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder_name: folderName, total_files: totalFiles }),
      signal,
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `Bulk ingest start failed (${res.status})`);
    }
    return res.json();
  }

  async bulkIngestUploadFile(
    jobId: string,
    file: File,
    signal?: AbortSignal,
  ): Promise<{ uploaded: number; total: number }> {
    const form = new FormData();
    form.append("file", file, file.name);
    const res = await fetch(this.url(`/ingest/bulk/${jobId}/files`), {
      method: "POST",
      body: form,
      signal,
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `Bulk upload failed (${res.status})`);
    }
    return res.json();
  }

  async bulkIngestRun(jobId: string, signal?: AbortSignal): Promise<{ queued: number }> {
    const res = await fetch(this.url(`/ingest/bulk/${jobId}/run`), {
      method: "POST",
      signal,
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `Bulk ingest queue failed (${res.status})`);
    }
    return res.json();
  }

  async bulkIngestResume(jobId: string, signal?: AbortSignal): Promise<{ queued: number }> {
    const res = await fetch(this.url(`/ingest/bulk/${jobId}/resume`), {
      method: "POST",
      signal,
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `Bulk ingest resume failed (${res.status})`);
    }
    return res.json();
  }

  async getBulkIngestJob(jobId: string, signal?: AbortSignal): Promise<BulkIngestJob> {
    const res = await fetch(this.url(`/ingest/bulk/${jobId}`), { signal });
    if (!res.ok) {
      throw new Error(`Bulk job status failed (${res.status})`);
    }
    return res.json();
  }

  async listDocuments(signal?: AbortSignal): Promise<DocumentSummary[]> {
    const res = await fetch(this.url("/admin/documents"), { signal });
    if (!res.ok) {
      throw new Error(`Failed to list documents (${res.status})`);
    }
    return res.json();
  }

  async getDocumentSuggestions(
    docId: string,
    signal?: AbortSignal,
  ): Promise<DocumentSuggestions> {
    const res = await fetch(
      this.url(`/admin/documents/${encodeURIComponent(docId)}/suggestions`),
      { signal },
    );
    if (!res.ok) {
      throw new Error(`Failed to load suggestions (${res.status})`);
    }
    return res.json();
  }

  async browseDirectories(path?: string, signal?: AbortSignal): Promise<DirectoryBrowseResponse> {
    const query = path ? `?path=${encodeURIComponent(path)}` : "";
    const res = await fetch(this.url(`/admin/directories${query}`), { signal });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `Failed to browse directories (${res.status})`);
    }
    return res.json();
  }

  async deleteDocument(docId: string, signal?: AbortSignal): Promise<void> {
    const res = await fetch(this.url(`/admin/doc/${encodeURIComponent(docId)}`), {
      method: "DELETE",
      signal,
    });
    if (!res.ok) {
      throw new Error(`Failed to delete document (${res.status})`);
    }
  }

  async ingestDirectory(
    directory: string,
    options?: { recursive?: boolean },
    signal?: AbortSignal,
  ): Promise<DirectoryIngestResponse> {
    const res = await fetch(this.url("/ingest/directory"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        directory,
        recursive: options?.recursive ?? true,
      }),
      signal,
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `Directory ingest failed (${res.status})`);
    }
    return res.json();
  }

  async query(
    body: {
      query: string;
      doc_id: string;
      top_k?: number;
      provider?: LlmProvider;
      retrieve_only?: boolean;
    },
    signal?: AbortSignal,
  ): Promise<QueryResponse> {
    const res = await fetch(this.url("/query"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        top_k: 8,
        provider: "openai",
        retrieve_only: false,
        ...body,
      }),
      signal,
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `Query failed (${res.status})`);
    }
    return res.json();
  }
}
