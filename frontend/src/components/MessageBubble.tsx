import type { ChatMessage } from "../types";
import { CitationsPanel } from "./CitationsPanel";
import { ConformityBanner } from "./ConformityBanner";
import { MessageContent } from "./MessageContent";

interface MessageBubbleProps {
  message: ChatMessage;
  onCitationPage?: (page: number) => void;
}

export function MessageBubble({ message, onCitationPage }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`message ${isUser ? "message-user" : "message-assistant"}`}>
      <div className="message-role">{isUser ? "You" : "DocuMind"}</div>
      <div className="message-body">
        {message.loading ? (
          <div className="typing">
            <span />
            <span />
            <span />
          </div>
        ) : (
          <MessageContent content={message.content} />
        )}
      </div>

      {!isUser && !message.loading && (
        <>
          {message.piiRedacted && (
            <p className="meta-note">Query was PII-redacted before retrieval.</p>
          )}
          {message.conformityReason && (
            <ConformityBanner reason={message.conformityReason} />
          )}
          {message.citations && message.citations.length > 0 && (
            <CitationsPanel citations={message.citations} onPageSelect={onCitationPage} />
          )}
          {message.latencyMs != null && (
            <p className="meta-note">{Math.round(message.latencyMs)} ms</p>
          )}
        </>
      )}
    </div>
  );
}
