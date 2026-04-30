import type { ErrorInfo } from "../hooks/useChat";

interface ErrorBannerProps {
  error: ErrorInfo;
  onDismiss: () => void;
  onRetry?: () => void;
}

const CATEGORY_ICONS: Record<string, string> = {
  auth: "\uD83D\uDD11",
  network: "\uD83C\uDF10",
  rate_limit: "\u23F3",
  billing: "\uD83D\uDCB3",
  warning: "\u26A0\uFE0F",
};

export default function ErrorBanner({ error, onDismiss, onRetry }: ErrorBannerProps) {
  const icon = CATEGORY_ICONS[error.category ?? ""] ?? "\u26A0\uFE0F";

  return (
    <div className="mx-6 mt-3 px-4 py-3 rounded-xl bg-red-500/5 border border-red-500/20 animate-fade-up">
      <div className="flex items-start gap-3">
        <span className="text-lg shrink-0 mt-0.5">{icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-red-400 break-words">{error.message}</p>
          {error.hint && (
            <p className="text-xs text-red-400/70 mt-1">{error.hint}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {error.retryable && onRetry && (
            <button
              onClick={onRetry}
              className="text-xs px-3 py-1.5 rounded-lg border border-red-500/30
                text-red-400 hover:bg-red-500/10 transition-colors"
            >
              Retry
            </button>
          )}
          <button
            onClick={onDismiss}
            aria-label="Dismiss error"
            className="text-red-400/50 hover:text-red-400 transition-colors p-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
