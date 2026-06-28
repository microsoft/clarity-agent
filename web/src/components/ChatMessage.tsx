import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage as ChatMessageType } from "../types";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    void navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <button
      onClick={handleCopy}
      title="Copy to clipboard"
      className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px]
        rounded text-body-faint transition-colors hover:bg-surface-hover hover:text-body"
    >
      <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="5.5" y="5.5" width="8" height="8" rx="1.5" />
        <path d="M10.5 5.5V3a1.5 1.5 0 0 0-1.5-1.5H3A1.5 1.5 0 0 0 1.5 3v6A1.5 1.5 0 0 0 3 10.5h2.5" />
      </svg>
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

interface ChatMessageProps {
  message: ChatMessageType;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const isTool = message.role === "tool";
  const hasContent = message.content.trim().length > 0;

  if (isTool || !hasContent) return null;

  // System messages: full-width, lighter styling
  if (isSystem) {
    return (
      <div className="flex justify-center">
        <div className="w-full max-w-xl px-4 py-2.5 rounded-lg bg-surface-muted/50 border border-border/50 text-center">
          {message.processName && (
            <span className="text-xs font-medium text-accent-focus">
              {message.processName}
            </span>
          )}
          <p className="text-xs text-body-muted mt-0.5">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`flex flex-col gap-1.5 ${isUser ? "max-w-[75%]" : "max-w-[85%]"}`}>
        {/* Message bubble */}
        <div
          className={`rounded-2xl px-5 py-3.5 ${
            isUser
              ? "bg-accent text-white shadow-md shadow-shadow-accent/10"
              : "bg-surface border border-border shadow-sm"
          }`}
        >
          {isUser ? (
            <p className="chat-text whitespace-pre-wrap leading-relaxed">{message.content}</p>
          ) : (
            <div className="prose max-w-none leading-relaxed chat-text">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Role label and copy action, below the bubble. */}
        <div className={`flex items-center gap-2 ${isUser ? "justify-end" : "justify-start"}`}>
          <span className="text-[10px] uppercase tracking-widest text-body-faint/50 px-1">
            {isUser ? "You" : "Clarity"}
          </span>
          {!isUser && <CopyButton text={message.content} />}
        </div>
      </div>
    </div>
  );
}
