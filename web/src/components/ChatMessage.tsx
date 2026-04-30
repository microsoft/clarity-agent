import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage as ChatMessageType } from "../types";

interface ChatMessageProps {
  message: ChatMessageType;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const isTool = message.role === "tool";

  // Tool messages: compact inline indicator
  if (isTool && message.toolEvents?.length) {
    return (
      <div className="flex justify-start">
        <div className="text-xs text-body-faint pl-1 font-mono">
          {message.toolEvents.map((te, i) => (
            <div key={i}>
              <span className="text-accent/60">{"\u2192"}</span> {te.tool}: {te.detail}
            </div>
          ))}
        </div>
      </div>
    );
  }

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
        {/* Tool events + cost log — visible above the message bubble */}
        {!isUser && (message.toolEvents?.length || message.costUsd || message.tokenCount) && (
          <div className="text-xs text-body-faint space-y-0.5 pl-1 font-mono">
            {message.toolEvents?.map((te, i) => (
              <div key={i}>
                <span className="text-accent/50">→</span> {te.tool}: {te.detail}
              </div>
            ))}
            {(message.tokenCount != null || message.costUsd != null) && (
              <div className="text-body-faint/60">
                {message.tokenCount != null && <>{message.tokenCount.toLocaleString()} tokens</>}
                {message.costUsd != null && <>{message.tokenCount != null ? " \u00b7 " : ""}${message.costUsd.toFixed(4)}</>}
              </div>
            )}
          </div>
        )}

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

        {/* Role label — subtle, below the bubble */}
        <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
          <span className="text-[10px] uppercase tracking-widest text-body-faint/50 px-1">
            {isUser ? "You" : "Clarity"}
          </span>
        </div>
      </div>
    </div>
  );
}
