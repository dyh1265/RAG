export interface Citation {
  doc_id: string;
  source_path: string;
  page_number: number | null;
  chunk_id: string;
  excerpt: string;
}

export interface RetrievedContext {
  chunk: {
    id: string;
    doc_id: string;
    chunk_type: string;
    content: string;
    page_number: number | null;
    section_path: string | null;
  };
  score: number;
  strategy: string;
  rank: number;
}

export interface ConformityMeta {
  score?: number;
  flagged?: boolean;
  reason?: string | null;
  forbidden_terms?: string[];
}

export interface QueryResponse {
  query: string;
  answer: string;
  citations: Citation[];
  retrieved_contexts: RetrievedContext[];
  model_used: string | null;
  latency_ms: number | null;
  metadata: {
    conformity?: ConformityMeta;
    conformity_blocked?: boolean;
  };
  pii_redacted: boolean;
}

export interface IngestResponse {
  doc_id: string;
  source_path: string;
  chunk_count: number;
  chunks_by_type: Record<string, number>;
  vectors_by_collection: Record<string, number>;
  errors: string[];
  skipped: boolean;
}

/** Live progress from POST /ingest/stream (SSE `progress` events). */
export interface IngestProgressEvent {
  stage: string;
  message: string;
  detail?: Record<string, unknown>;
}

export interface HealthResponse {
  status: string;
}

export interface ReadyResponse {
  status: string;
  checks: Record<string, string>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  conformityReason?: string;
  latencyMs?: number;
  piiRedacted?: boolean;
  loading?: boolean;
}

export interface DirectoryEntry {
  name: string;
  path: string;
  kind: "directory" | "file";
  pdf: boolean;
}

export interface DirectoryBrowseResponse {
  path: string;
  parent: string | null;
  entries: DirectoryEntry[];
}

export interface DirectoryIngestResponse {
  directory: string;
  total_files: number;
  ingested: number;
  skipped: number;
  failed: number;
  documents: IngestResponse[];
}

export type LlmProvider = "openai" | "ollama";

export interface BulkIngestStartResponse {
  job_id: string;
  total_files: number;
}

export interface BulkIngestJob {
  job_id: string;
  folder_name: string;
  status: "uploading" | "queued" | "running" | "done" | "error";
  total: number;
  uploaded: number;
  processed: number;
  ingested: number;
  skipped: number;
  failed: number;
  current_file?: string | null;
  message?: string | null;
}

export interface DocumentSummary {
  doc_id: string;
  name: string;
  source_path?: string;
  chunk_count: number;
}

export interface DocumentSuggestions {
  doc_id: string;
  questions: string[];
}

export interface RecentDocument {
  docId: string;
  name: string;
  chunkCount: number;
  ingestedAt: string;
  sourcePath?: string;
}

export type FolderLoadSource = "local" | "server";

export interface FolderLoadProgress {
  status: "running" | "done" | "error";
  source: FolderLoadSource;
  folderName?: string;
  total: number;
  processed: number;
  ingested: number;
  skipped: number;
  failed: number;
  currentFile?: string;
  message?: string;
}
