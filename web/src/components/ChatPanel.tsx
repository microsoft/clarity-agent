import { useEffect, useLayoutEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getProtocolTree, getSession } from "../api/client";
import { useChat } from "../hooks/useChat";
import type { SessionInfo } from "../types";
import ChatMessage from "./ChatMessage";
import EmptyState from "./EmptyState";
import ErrorBanner from "./ErrorBanner";
import MessageInput from "./MessageInput";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export default function ChatPanel() {
  const {
    messages,
    turnCost,
    turnTokens,
    sessionTokens,
    sessionCost,
    streamingText,
    queuedMessages,
    streaming,
    currentProcess,
    connected,
    error,
    statusPhase,
    historyLoaded,
    sendMessage,
    startProcess,
    stopGeneration,
    startNewChapter,
    dismissError,
  } = useChat();

  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  /** True when the user is scrolled to the bottom (or close to it). */
  const stickToBottom = useRef(true);
  const autoStarted = useRef(false);
  const [protocolExists, setProtocolExists] = useState<boolean | null>(null);
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);

  // Check if a protocol directory exists
  useEffect(() => {
    getProtocolTree()
      .then((tree) => setProtocolExists(tree.exists))
      .catch(() => setProtocolExists(null));
  }, []);

  // Fetch session info (for print header).
  useEffect(() => {
    getSession().then(setSessionInfo).catch(() => {});
  }, []);

  // Auto-start the clarity-agent process — but only when this is
  // genuinely a fresh start.  The ``historyLoaded`` guard is the
  // key new piece: if the user has prior conversation in the
  // current chapter, the load_history fetch will populate
  // ``messages`` and the ``messages.length === 0`` check below
  // becomes false, so we skip the slow kickoff and let them resume.
  // Without ``historyLoaded`` we'd race the fetch and fire the
  // kickoff on every page open.
  useEffect(() => {
    if (
      historyLoaded
      && connected
      && !autoStarted.current
      && messages.length === 0
      && !streaming
      && protocolExists !== false
    ) {
      autoStarted.current = true;
      startProcess("clarity-agent");
    }
  }, [historyLoaded, connected, messages.length, streaming, startProcess, protocolExists]);

  // Track whether the user is scrolled to the bottom. Only auto-scroll
  // when they're "stuck" to the bottom — if they've scrolled up to read
  // earlier content, don't yank them back down on each streaming update.
  const handleScroll = () => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickToBottom.current = distanceFromBottom < 80;
  };

  // Pin to the bottom on mount or when history first arrives —
  // before the browser paints, with no animation — so the user
  // doesn't see the top of the conversation flash by before the
  // smooth-scroll catches up.  Runs once per mount (re-mounts on
  // tab-switch back to Session get a fresh ref and re-pin).
  const initialScrollDone = useRef(false);
  const hasContent = messages.length > 0;
  useLayoutEffect(() => {
    if (initialScrollDone.current || !hasContent) return;
    initialScrollDone.current = true;
    bottomRef.current?.scrollIntoView({ behavior: "instant" as ScrollBehavior });
  }, [hasContent]);

  // Live updates — streaming text, new turns after the initial
  // load — get smooth scroll, only when the user is stuck to the
  // bottom (so reading earlier turns isn't disrupted).
  useEffect(() => {
    if (!initialScrollDone.current) return;
    if (stickToBottom.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, streamingText]);

  return (
    <div className="flex flex-col h-full">
      {/* Header bar */}
      <div className="print-hide flex items-center justify-between px-6 py-3.5 border-b border-border bg-surface/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <h2
            className="text-lg text-body-heading font-display"
          >
            Clarity Agent
          </h2>
          {currentProcess && (
            <span className="text-xs text-body-faint bg-surface-muted px-2 py-0.5 rounded-full">
              {currentProcess}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <span
            className={`inline-flex items-center gap-1.5 text-xs ${
              connected ? "text-body-muted" : "text-status-error"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full transition-colors ${
                connected ? "bg-accent-focus" : "bg-status-error animate-pulse"
              }`}
            />
            {connected ? "Connected" : "Disconnected"}
          </span>
          {/* Session usage counter */}
          {sessionTokens > 0 && (
            <span
              className="text-xs text-body-faint font-mono tabular-nums"
              role="status"
              aria-label={`Session usage: ${formatTokens(sessionTokens)} tokens${sessionCost > 0 ? `, $${sessionCost.toFixed(4)}` : ""}`}
            >
              {formatTokens(sessionTokens)} tokens
              {sessionCost > 0 && <>{" \u00b7 "}${sessionCost.toFixed(4)}</>}
            </span>
          )}
          <button
            onClick={() => {
              // Friction proportional to consequence: archiving the
              // current chapter is reversible (the old chapter stays
              // browsable in History), but the active conversation
              // does end.  A simple confirm() is unambiguous and
              // matches the destructiveness-tier the user agreed to.
              const ok = window.confirm(
                "Start a new chapter?\n\n" +
                "The current conversation will be archived (you can " +
                "still read it in History), and the next message will " +
                "start a fresh conversation with no carried-over context.",
              );
              if (!ok) return;
              // Allow the auto-start effect to re-fire the
              // clarity-agent process kickoff on the new chapter.
              autoStarted.current = false;
              void startNewChapter();
            }}
            disabled={streaming}
            aria-label="Start a new chapter in this conversation thread"
            className="text-xs px-3.5 py-1.5 border border-border-strong rounded-lg
              text-body-label hover:bg-surface-dim hover:border-accent/30
              disabled:opacity-40 disabled:cursor-not-allowed
              transition-all duration-200"
          >
            New Chapter
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <ErrorBanner
          error={error}
          onDismiss={dismissError}
          onRetry={error.retryable ? () => {
            dismissError();
            // Re-send the last user message if there is one
            const lastUserMsg = [...messages].reverse().find(m => m.role === "user");
            if (lastUserMsg) sendMessage(lastUserMsg.content);
          } : undefined}
        />
      )}

      {/* Messages — bottom-anchored so content grows upward from input */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-auto bg-surface-ground/50"
        data-printable
        role="log"
        aria-label="Chat messages"
        aria-live="polite"
      >
        {/* Print-only header — hidden on screen, shown when printing */}
        {sessionInfo && (
          <div className="print-header hidden print:block px-6 pt-4 pb-2 border-b border-gray-300">
            <div className="text-lg font-bold text-black">
              {sessionInfo.project_dir.split("/").filter(Boolean).pop() || "Clarity"}
            </div>
            <div className="text-xs text-gray-500">
              Thread: {sessionInfo.thread_id || "—"}
              {" · "}
              {new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}
            </div>
          </div>
        )}
        <div className="flex flex-col justify-end min-h-full max-w-3xl mx-auto px-6 py-6 space-y-5">
          {messages.length === 0 && !streaming && protocolExists === false && connected && (
            <EmptyState
              heading="What are you working on?"
              description="Clarity helps you think through problems, design solutions, and anticipate failures — structured thinking with AI guidance."
              actions={[
                {
                  label: "Start a new project",
                  primary: true,
                  onClick: () => {
                    autoStarted.current = true;
                    startProcess("problem-clarification");
                  },
                },
                {
                  label: "Review an existing project",
                  onClick: () => {
                    autoStarted.current = true;
                    startProcess("clarity-agent");
                  },
                },
                {
                  label: "Just chat",
                  onClick: () => {
                    autoStarted.current = true;
                    sendMessage("Hi! I'd like to discuss something.");
                  },
                },
              ]}
            />
          )}

          {messages.length === 0 && !streaming && protocolExists !== false && (
            <div className="text-center py-16 animate-fade-up">
              <h2 className="text-3xl text-body-heading mb-2 font-display">
                What are you working on?
              </h2>
              <p className="text-sm text-body-muted max-w-md mx-auto leading-relaxed">
                {connected
                  ? "Starting the clarity process — I'll help you think through your project."
                  : "Connecting to the Clarity Agent..."}
              </p>
            </div>
          )}

          {messages.map((msg, i) => {
            // Collapse vertical spacing between consecutive tool messages:
            // only the first tool in a run gets the normal space-y-5 gap,
            // later ones cancel it out with -mt-5.
            const prev = i > 0 ? messages[i - 1] : null;
            const collapseTop = msg.role === "tool" && prev?.role === "tool";
            return (
              <div
                key={msg.id}
                className={`animate-fade-up ${collapseTop ? "-mt-5" : ""}`}
                style={{ animationDelay: `${Math.min(i * 50, 300)}ms` }}
              >
                <ChatMessage message={msg} />
              </div>
            );
          })}

          {/* Streaming: live text bubble + status bar */}
          {streaming && (
            <div className="space-y-2 animate-fade-in" role="status" aria-label="Generating response">
              {/* Live text — rendered as markdown like final messages */}
              {streamingText && (
                <div className="flex justify-start">
                  <div className="max-w-[85%] rounded-2xl px-5 py-3.5 bg-surface border border-border shadow-sm">
                    <div className="prose max-w-none leading-relaxed chat-text">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {streamingText}
                      </ReactMarkdown>
                    </div>
                  </div>
                </div>
              )}

              {/* Status bar: dots + cost + stop */}
              <div className="flex justify-start">
                <div className="flex items-center gap-3 px-2">
                  <div className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" />
                    <span
                      className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce"
                      style={{ animationDelay: "0.15s" }}
                    />
                    <span
                      className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce"
                      style={{ animationDelay: "0.3s" }}
                    />
                  </div>
                  {statusPhase && (
                    <span className="text-xs text-body-muted italic">
                      {statusPhase}
                    </span>
                  )}
                  {(turnTokens > 0 || turnCost > 0) && (
                    <span
                      className="text-xs text-body-faint font-mono tabular-nums"
                      aria-label={`Turn usage: ${turnTokens > 0 ? formatTokens(turnTokens) + " tokens" : ""}${turnCost > 0 ? `, $${turnCost.toFixed(4)}` : ""}`}
                    >
                      {turnTokens > 0 && <>{formatTokens(turnTokens)} tokens</>}
                      {turnCost > 0 && <>{turnTokens > 0 ? " \u00b7 " : ""}${turnCost.toFixed(4)}</>}
                    </span>
                  )}
                  <button
                    onClick={stopGeneration}
                    aria-label="Stop generating"
                    className="w-6 h-6 flex items-center justify-center rounded-full border border-border text-body-muted
                      hover:border-accent/40 hover:text-accent-focus hover:bg-accent-focus/5 transition-all"
                  >
                    <svg className="w-2.5 h-2.5" viewBox="0 0 10 10" fill="currentColor">
                      <rect width="10" height="10" rx="1" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input */}
      <div className="print-hide">
        <MessageInput
          onSend={sendMessage}
          // Only disable when fully disconnected — typing while
          // streaming is fine, messages are queued and sent in turn.
          disabled={!connected}
          // Identify this chat panel so its draft text survives
          // mount/unmount (e.g., navigating to documents and
          // back).  ``project_id`` is preferred when the backend
          // provides it (a stable canonical identifier);
          // ``project_dir`` is the path-based fallback that's
          // always present.  Both names live on ``SessionInfo``;
          // pass null until ``getSession()`` resolves so the input
          // stays ephemeral during the brief loading window
          // instead of binding to a placeholder id.
          panelId={
            sessionInfo && sessionInfo.thread_id
              ? {
                  projectId:
                    sessionInfo.project_id ?? sessionInfo.project_dir,
                  type: "chat",
                  threadId: sessionInfo.thread_id,
                }
              : null
          }
          placeholder={
            !connected
              ? "Connecting..."
              : queuedMessages > 0
                ? `${queuedMessages} message${queuedMessages === 1 ? "" : "s"} queued — type another...`
                : streaming
                  ? "Type your next message — it'll send when this turn finishes..."
                  : undefined
          }
        />
      </div>
    </div>
  );
}
