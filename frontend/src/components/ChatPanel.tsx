import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "../types";
import { MessageBubble } from "./MessageBubble";

interface ChatPanelProps {
  messages: ChatMessage[];
  onSend: (query: string) => void;
  onClearChat: () => void;
  onCitationPage?: (page: number) => void;
  disabled: boolean;
  docId: string;
  docName?: string;
  suggestions?: string[];
  suggestionsLoading?: boolean;
}

export function ChatPanel({
  messages,
  onSend,
  onClearChat,
  onCitationPage,
  disabled,
  docId,
  docName,
  suggestions = [],
  suggestionsLoading = false,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setInput("");
  };

  return (
    <div className="chat-panel">
      <div className="chat-doc-bar">
        <div className="chat-doc-label">
          {docName ? (
            <>
              <strong>{docName}</strong>
              <span className="chat-doc-id"> · {docId}</span>
            </>
          ) : (
            <>
              Document <code>{docId}</code>
            </>
          )}
        </div>
        {messages.length > 0 && (
          <button
            type="button"
            className="btn btn-ghost btn-sm chat-clear-btn"
            onClick={onClearChat}
            disabled={disabled}
          >
            Clear chat
          </button>
        )}
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>Ask anything about the uploaded document.</p>
            <div className="suggestions">
              {suggestionsLoading && suggestions.length === 0 ? (
                <p className="suggestions-loading">Loading suggestions…</p>
              ) : (
                suggestions.map((q) => (
                  <button
                    key={q}
                    type="button"
                    className="suggestion-chip"
                    disabled={disabled}
                    onClick={() => onSend(q)}
                  >
                    {q}
                  </button>
                ))
              )}
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} onCitationPage={onCitationPage} />
        ))}
        <div ref={bottomRef} />
      </div>

      <form className="chat-input-row" onSubmit={submit}>
        <input
          className="chat-input"
          type="text"
          placeholder="Ask about the document…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={disabled}
          autoFocus
        />
        <button type="submit" className="btn btn-primary" disabled={disabled || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
