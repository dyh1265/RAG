import type { DocumentSummary, RecentDocument } from "../types";

const RECENT_KEY = "documind.recentDocs";
const ACTIVE_KEY = "documind.activeDocId";
const MAX_RECENT = 20;

export function loadRecentDocuments(): RecentDocument[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as RecentDocument[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveRecentDocuments(docs: RecentDocument[]): void {
  localStorage.setItem(RECENT_KEY, JSON.stringify(docs.slice(0, MAX_RECENT)));
}

export function addRecentDocument(entry: Omit<RecentDocument, "ingestedAt">): RecentDocument[] {
  const doc: RecentDocument = { ...entry, ingestedAt: new Date().toISOString() };
  const without = loadRecentDocuments().filter((d) => d.docId !== doc.docId);
  const next = [doc, ...without].slice(0, MAX_RECENT);
  saveRecentDocuments(next);
  return next;
}

export function removeRecentDocument(docId: string): RecentDocument[] {
  const next = loadRecentDocuments().filter((d) => d.docId !== docId);
  saveRecentDocuments(next);
  return next;
}

export function loadActiveDocId(): string | null {
  return localStorage.getItem(ACTIVE_KEY);
}

export function saveActiveDocId(docId: string | null): void {
  if (docId) {
    localStorage.setItem(ACTIVE_KEY, docId);
  } else {
    localStorage.removeItem(ACTIVE_KEY);
  }
}

export function basenameFromPath(path: string, docId: string): string {
  const parts = path.replace(/\\/g, "/").split("/");
  const name = parts[parts.length - 1];
  return name && name !== path ? name : `${docId.slice(0, 12)}…`;
}

/** Merge local recency order with API-indexed documents. */
export function mergeDocumentLists(
  recent: RecentDocument[],
  indexed: DocumentSummary[],
): RecentDocument[] {
  const byId = new Map<string, RecentDocument>();

  for (const doc of recent) {
    byId.set(doc.docId, doc);
  }

  for (const row of indexed) {
    const existing = byId.get(row.doc_id);
    if (existing) {
      byId.set(row.doc_id, {
        ...existing,
        name: existing.name || row.name,
        chunkCount: row.chunk_count || existing.chunkCount,
        sourcePath: row.source_path || existing.sourcePath,
      });
    } else {
      byId.set(row.doc_id, {
        docId: row.doc_id,
        name: row.name,
        chunkCount: row.chunk_count,
        ingestedAt: "",
        sourcePath: row.source_path || undefined,
      });
    }
  }

  const recentIds = recent.map((d) => d.docId);
  const ordered: RecentDocument[] = [];

  for (const id of recentIds) {
    const doc = byId.get(id);
    if (doc) {
      ordered.push(doc);
      byId.delete(id);
    }
  }

  const rest = [...byId.values()].sort((a, b) => a.name.localeCompare(b.name));
  return [...ordered, ...rest];
}
