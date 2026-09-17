import { useState } from "react";
import { sendFeedback } from "../api/client";

interface FeedbackDialogProps {
  onClose: () => void;
}

export default function FeedbackDialog({ onClose }: FeedbackDialogProps) {
  const [message, setMessage] = useState("");
  const [contactOk, setContactOk] = useState(false);
  const [contactEmail, setContactEmail] = useState("");
  const [includeLlmInfo, setIncludeLlmInfo] = useState(true);
  const [includeTranscript, setIncludeTranscript] = useState(false);
  const [transcriptTurns, setTranscriptTurns] = useState(5);
  const [context, setContext] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issueUrl, setIssueUrl] = useState<string | null>(null);

  const canSend = message.trim().length > 0 && !issueUrl;

  const handleSubmit = async () => {
    if (!canSend) return;
    setSending(true);
    setError(null);
    try {
      const result = await sendFeedback({
        message,
        contact_ok: contactOk,
        contact_email: contactEmail,
        include_llm_info: includeLlmInfo,
        transcript_turns: includeTranscript ? transcriptTurns : 0,
        context,
      });

      setIssueUrl(result.issue_url);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-surface rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-border">
          <h2 className="text-lg font-display text-body-heading">Send Feedback</h2>
          <button
            onClick={onClose}
            aria-label="Close feedback dialog"
            className="p-1 text-body-faint hover:text-body-muted transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {/* Message */}
          <div>
            <label htmlFor="feedback-message" className="block text-xs text-body-label mb-1.5">
              Your message
            </label>
            <textarea
              id="feedback-message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              disabled={!!issueUrl}
              placeholder="Tell us what you think, report a bug, or suggest an improvement..."
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface-ground
                text-sm text-body-heading placeholder:text-body-faint
                focus:outline-none focus:border-accent-focus focus:ring-1 focus:ring-accent-focus/30
                disabled:opacity-60 transition-all resize-y"
            />
          </div>

          {/* Contact permission */}
          <div className="space-y-2">
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={contactOk}
                disabled={!!issueUrl}
                onChange={(e) => setContactOk(e.target.checked)}
                className="rounded border-border text-accent-focus focus:ring-accent-focus/30"
              />
              <span className="text-sm text-body-heading">
                You may contact me for more information
              </span>
            </label>
            {contactOk && (
              <input
                type="email"
                value={contactEmail}
                disabled={!!issueUrl}
                onChange={(e) => setContactEmail(e.target.value)}
                placeholder="your@email.com"
                className="w-full px-3 py-2 rounded-lg border border-border bg-surface-ground
                  text-sm text-body-heading placeholder:text-body-faint
                  focus:outline-none focus:border-accent-focus focus:ring-1 focus:ring-accent-focus/30
                  disabled:opacity-60 transition-all ml-6"
                style={{ width: "calc(100% - 1.5rem)" }}
              />
            )}
          </div>

          {/* Attachments */}
          <div className="space-y-2">
            <p className="text-xs text-body-label">Include with feedback:</p>

            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={includeLlmInfo}
                disabled={!!issueUrl}
                onChange={(e) => setIncludeLlmInfo(e.target.checked)}
                className="rounded border-border text-accent-focus focus:ring-accent-focus/30"
              />
              <span className="text-sm text-body-heading">
                LLM backend and model info
              </span>
            </label>

            <div className="space-y-1.5">
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeTranscript}
                  disabled={!!issueUrl}
                  onChange={(e) => setIncludeTranscript(e.target.checked)}
                  className="rounded border-border text-accent-focus focus:ring-accent-focus/30"
                />
                <span className="text-sm text-body-heading">
                  Recent transcript
                </span>
              </label>
              {includeTranscript && (
                <div className="flex items-center gap-2 ml-6">
                  <span className="text-xs text-body-muted">Last</span>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={transcriptTurns}
                    disabled={!!issueUrl}
                    onChange={(e) => setTranscriptTurns(Math.max(1, parseInt(e.target.value) || 1))}
                    className="w-16 px-2 py-1 rounded border border-border bg-surface-ground
                      text-sm text-body-heading text-center
                      focus:outline-none focus:border-accent-focus focus:ring-1 focus:ring-accent-focus/30
                      disabled:opacity-60 transition-all"
                  />
                  <span className="text-xs text-body-muted">turns</span>
                </div>
              )}
            </div>

            <label htmlFor="feedback-context" className="block text-xs text-body-label">
              Other relevant context (optional)
            </label>
            <textarea
              id="feedback-context"
              value={context}
              onChange={(e) => setContext(e.target.value)}
              rows={2}
              disabled={!!issueUrl}
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface-ground
                text-sm text-body-heading focus:outline-none focus:border-accent-focus
                focus:ring-1 focus:ring-accent-focus/30 disabled:opacity-60 transition-all resize-y"
            />
          </div>

          {/* Privacy notice — shown before submission */}
          {!issueUrl && (
            <p className="text-xs text-body-faint leading-relaxed">
              The information you select will be shared with the Clarity Agent
              team and used to improve the product.
            </p>
          )}

          {issueUrl && (
            <div className="p-3 rounded-lg border border-green-500/20 bg-green-500/5 text-sm">
              <p className="text-green-400">
                Your feedback is ready to review on GitHub.
              </p>
              <a
                href={issueUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block mt-2 text-accent-focus hover:underline"
              >
                Review and create issue
              </a>
            </div>
          )}

          {/* Error */}
          {error && (
            <p className="text-sm text-status-error-text bg-status-error-bg rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-border">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg text-body-muted
              hover:text-body hover:bg-surface-dim transition-colors"
          >
            {issueUrl ? "Done" : "Cancel"}
          </button>
          {!issueUrl && (
            <button
              onClick={handleSubmit}
              disabled={!canSend || sending}
              className="px-4 py-2 text-sm rounded-lg bg-accent-focus text-white
                hover:brightness-110 disabled:opacity-40 transition-all"
            >
              {sending ? "Preparing..." : "Prepare GitHub Issue"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
