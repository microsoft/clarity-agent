import { useEffect, useRef, useState, type PointerEvent } from "react";
import type { ToolEvent } from "../types";

const COLLAPSED_PANE_WIDTH = 56;
const MIN_PANE_WIDTH = 320;
const MAX_PANE_WIDTH = 760;
const UNREAD_BADGE_LIMIT = 99;

interface ToolLogPaneProps {
  events: ToolEvent[];
  open: boolean;
  unread: boolean;
  width: number;
  onOpenChange: (open: boolean) => void;
  onWidthChange: (width: number) => void;
}

function clampPaneWidth(width: number): number {
  return Math.min(MAX_PANE_WIDTH, Math.max(MIN_PANE_WIDTH, width));
}

function formatToolCommand(event: ToolEvent): string {
  const detail = event.detail.trim();
  if (!detail) return `${event.tool}: executing`;
  return `${event.tool}: ${detail}`;
}

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
      type="button"
      onClick={handleCopy}
      className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-[11px] text-white/65 transition-colors hover:bg-white/10 hover:text-white sm:px-2"
      title="Copy log"
      aria-label="Copy log"
    >
      <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="5.5" y="5.5" width="8" height="8" rx="1.5" />
        <path d="M10.5 5.5V3a1.5 1.5 0 0 0-1.5-1.5H3A1.5 1.5 0 0 0 1.5 3v6A1.5 1.5 0 0 0 3 10.5h2.5" />
      </svg>
      <span className="hidden sm:inline">{copied ? "Copied" : "Copy"}</span>
    </button>
  );
}

export default function ToolLogPane({
  events,
  open,
  unread,
  width,
  onOpenChange,
  onWidthChange,
}: ToolLogPaneProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const dragCleanupRef = useRef<(() => void) | null>(null);
  const commands = events.map(formatToolCommand);
  const script = commands.map((command) => `PS clarity> ${command}`).join("\n");
  const paneWidth = open ? clampPaneWidth(width) : COLLAPSED_PANE_WIDTH;

  useEffect(() => {
    if (!open) return;
    if (typeof bottomRef.current?.scrollIntoView !== "function") return;
    bottomRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [events.length, open]);

  useEffect(() => {
    return () => dragCleanupRef.current?.();
  }, []);

  if (events.length === 0 && !open) return null;

  const handleResizeStart = (event: PointerEvent<HTMLButtonElement>) => {
    event.preventDefault();
    dragCleanupRef.current?.();
    const startX = event.clientX;
    const startWidth = paneWidth;

    const handleResizeMove = (moveEvent: globalThis.PointerEvent) => {
      onWidthChange(clampPaneWidth(startWidth + startX - moveEvent.clientX));
    };
    const handleResizeEnd = () => {
      window.removeEventListener("pointermove", handleResizeMove);
      window.removeEventListener("pointerup", handleResizeEnd);
      dragCleanupRef.current = null;
    };

    window.addEventListener("pointermove", handleResizeMove);
    window.addEventListener("pointerup", handleResizeEnd);
    dragCleanupRef.current = handleResizeEnd;
  };

  return (
    <aside
      aria-label="Execution log"
      data-open={open ? "true" : "false"}
      data-testid="log-side-pane"
      className="print-hide relative flex h-full shrink-0 overflow-hidden border-l border-white/10 bg-[#0b1115] text-white transition-[width] duration-300 ease-out"
      style={{
        width: `${paneWidth}px`,
        maxWidth: open ? "100%" : `${COLLAPSED_PANE_WIDTH}px`,
      }}
    >
      {!open ? (
        <div className="flex h-full w-full items-start justify-center bg-surface/95 pt-4">
          <button
            type="button"
            onClick={() => onOpenChange(true)}
            aria-label="Open execution log"
            aria-expanded="false"
            title="Open execution log"
            data-testid="log-pane-toggle"
            data-unread={unread ? "true" : "false"}
            className={`relative flex h-10 w-10 items-center justify-center rounded-full border border-border-strong bg-surface text-body-muted shadow-lg transition-all duration-200 hover:border-accent/50 hover:text-accent-focus ${
              unread
                ? "border-accent/70 text-accent-focus shadow-[0_0_0_4px_rgba(20,184,166,0.12),0_0_28px_rgba(20,184,166,0.55)]"
                : ""
            }`}
          >
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="m8 9 3 3-3 3" />
              <path d="M13 15h3" />
              <rect x="3.5" y="5" width="17" height="14" rx="2" />
            </svg>
            <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-[#14b8a6] px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white shadow-sm">
              {events.length > UNREAD_BADGE_LIMIT ? `${UNREAD_BADGE_LIMIT}+` : events.length}
            </span>
          </button>
        </div>
      ) : (
        <div className="flex min-w-0 flex-1 flex-col">
          <button
            type="button"
            onPointerDown={handleResizeStart}
            aria-label="Resize execution log"
            data-testid="log-pane-resize-handle"
            className="absolute left-0 top-0 z-10 h-full w-2 cursor-col-resize border-l border-[#14b8a6]/0 transition-colors hover:border-[#14b8a6]/70 focus:outline-none focus-visible:border-[#14b8a6]"
          />
          <div className="flex items-center justify-between border-b border-white/10 bg-[#121a20] px-2 py-3 sm:px-4">
            <div className="min-w-0">
              <div className="truncate font-mono text-xs uppercase tracking-[0.16em] text-white/55">
                Execution Log
              </div>
              <div className="mt-0.5 text-xs text-white/40">
                {events.length} {events.length === 1 ? "line" : "lines"}
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <CopyButton text={script} />
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="flex h-7 w-7 items-center justify-center rounded text-white/55 transition-colors hover:bg-white/10 hover:text-white"
                aria-label="Close execution log"
                title="Close execution log"
              >
                <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
                  <path d="M4 4l8 8M12 4l-8 8" />
                </svg>
              </button>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-auto px-4 py-3">
            {commands.length === 0 ? (
              <span className="font-mono text-xs text-white/35">Waiting for logs…</span>
            ) : (
            <pre className="m-0 whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-[#d6e2ef]">
              {commands.map((command, index) => (
                <span className="block" key={`${command}-${index}`}>
                  <span className="text-[#5eead4]">PS clarity&gt;</span>{" "}
                  <code>{command}</code>
                </span>
              ))}
            </pre>
            )}
            <div ref={bottomRef} />
          </div>
        </div>
      )}
    </aside>
  );
}
