import type { ChatMessage } from "../types";

const CHATS_KEY = "documind.chats";
const MAX_MESSAGES_PER_DOC = 100;

type ChatStore = Record<string, ChatMessage[]>;

function readStore(): ChatStore {
  try {
    const raw = localStorage.getItem(CHATS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as ChatStore;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeStore(store: ChatStore): void {
  localStorage.setItem(CHATS_KEY, JSON.stringify(store));
}

/** Persisted messages only — never store in-flight loading placeholders. */
export function sanitizeForStorage(messages: ChatMessage[]): ChatMessage[] {
  return messages.filter((m) => !m.loading).slice(-MAX_MESSAGES_PER_DOC);
}

export function loadChat(docId: string): ChatMessage[] {
  return readStore()[docId] ?? [];
}

export function saveChat(docId: string, messages: ChatMessage[]): void {
  const store = readStore();
  const cleaned = sanitizeForStorage(messages);
  if (cleaned.length === 0) {
    delete store[docId];
  } else {
    store[docId] = cleaned;
  }
  writeStore(store);
}

export function clearChat(docId: string): void {
  const store = readStore();
  delete store[docId];
  writeStore(store);
}
