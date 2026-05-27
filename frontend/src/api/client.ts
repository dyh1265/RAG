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
import { parseApiErrorBody } from "../utils/apiErrors";

const STORAGE_KEY = "documind.apiUrl";

/** Read an errored Response and throw a short user-facing message.
 * Never throws a raw nginx/Cloudflare HTML page into the UI. */
async function throwApiError(res: Response, fallback: string): Promise<never> {
  let body = "";
  try {
    body = await res.text();
  } catch {
    /* body already consumed or aborted — keep going with the fallback */
  }
  throw new Error(parseApiErrorBody(body, res.status) || `${fallback} (${res.status})`);
}

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
    // When the SPA is served same-origin, prefer the `/api` proxy: cross-port
    // fetch from a hashed Vite bundle to a different host port often fails in
    // embedded browsers (e.g. the Cloudflare Tunnel preview).
    const sameOrigin = window.location.protocol === "http:" || window.location.protocol === "https:";
    if (sameOrigin && normalized === "http://localhost:8002" && window.location.port !== "8002") {
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
    if (!res.ok) await throwApiError(res, "Health check failed");
    return res.json();
  }

  async ready(signal?: AbortSignal): Promise<ReadyResponse> {
    const res = await fetchWithTimeout(
      this.url("/ready"),
      { signal },
      RagApiClient.CONNECT_TIMEOUT_MS,
    );
    if (!res.ok) await throwApiError(res, "Not ready");
    return res.json();
  }

  async ingest(file: File, signal?: AbortSignal): Promise<IngestResponse> {
    const form = new FormData();
    form.append("file", file, file.name);
    const res = await fetch(this.url("/ingest"), {
      method: "POST",
      body: form,
      signal,
    });
    if (!res.ok) await throwApiError(res, "Ingest failed");
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
    if (!res.ok) await throwApiError(res, "Bulk ingest start failed");
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
    if (!res.ok) await throwApiError(res, "Bulk upload failed");
    return res.json();
  }

  async bulkIngestRun(jobId: string, signal?: AbortSignal): Promise<{ queued: number }> {
    const res = await fetch(this.url(`/ingest/bulk/${jobId}/run`), {
      method: "POST",
      signal,
    });
    if (!res.ok) await throwApiError(res, "Bulk ingest queue failed");
    return res.json();
  }

  async bulkIngestResume(jobId: string, signal?: AbortSignal): Promise<{ queued: number }> {
    const res = await fetch(this.url(`/ingest/bulk/${jobId}/resume`), {
      method: "POST",
      signal,
    });
    if (!res.ok) await throwApiError(res, "Bulk ingest resume failed");
    return res.json();
  }

  async getBulkIngestJob(jobId: string, signal?: AbortSignal): Promise<BulkIngestJob> {
    const res = await fetch(this.url(`/ingest/bulk/${jobId}`), { signal });
    if (!res.ok) await throwApiError(res, "Bulk job status failed");
    return res.json();
  }

  async listDocuments(signal?: AbortSignal): Promise<DocumentSummary[]> {
    const res = await fetch(this.url("/admin/documents"), { signal });
    if (!res.ok) await throwApiError(res, "Failed to list documents");
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
    if (!res.ok) await throwApiError(res, "Failed to load suggestions");
    return res.json();
  }

  async browseDirectories(path?: string, signal?: AbortSignal): Promise<DirectoryBrowseResponse> {
    const query = path ? `?path=${encodeURIComponent(path)}` : "";
    const res = await fetch(this.url(`/admin/directories${query}`), { signal });
    if (!res.ok) await throwApiError(res, "Failed to browse directories");
    return res.json();
  }

  async deleteDocument(docId: string, signal?: AbortSignal): Promise<void> {
    const res = await fetch(this.url(`/admin/doc/${encodeURIComponent(docId)}`), {
      method: "DELETE",
      signal,
    });
    if (!res.ok) await throwApiError(res, "Failed to delete document");
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
    if (!res.ok) await throwApiError(res, "Directory ingest failed");
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
    if (!res.ok) await throwApiError(res, "Query failed");
    return res.json();
  }
}
