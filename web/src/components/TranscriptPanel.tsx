import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getTranscript, getTranscripts } from "../api/client";
import type { TranscriptEntry } from "../types";

export default function TranscriptPanel() {
  const [transcripts, setTranscripts] = useState<TranscriptEntry[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getTranscripts()
      .then((data) => setTranscripts(data.transcripts))
      .catch(() => {});
  }, []);

  const selectTranscript = useCallback((name: string) => {
    setSelected(name);
    setLoading(true);
    getTranscript(name)
      .then((data) => setContent(data.content))
      .catch((err) => setContent(`Error: ${err.message}`))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex h-full">
      {/* Transcript list */}
      <div className="w-64 border-r border-border overflow-auto bg-surface print-hide">
        <div className="px-5 py-4 border-b border-border">
          <h2
            className="text-sm text-body-heading font-display"
          >
            Chat History
          </h2>
          <p className="text-xs text-body-faint mt-0.5">{transcripts.length} session(s)</p>
        </div>
        <div className="py-2">
          {transcripts.length === 0 && (
            <p className="px-5 py-4 text-xs text-body-faint animate-fade-up">
              No transcripts yet.
            </p>
          )}
          {transcripts.map((t, i) => (
            <button
              key={t.name}
              onClick={() => selectTranscript(t.name)}
              className={`w-full text-left px-5 py-3 transition-all duration-150
                animate-fade-up ${
                  selected === t.name
                    ? "bg-accent-surface text-accent-surface-body border-l-2 border-accent -ml-px"
                    : "text-body-label hover:bg-surface-dim"
                }`}
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <p
                className="text-xs truncate font-mono"
              >
                {t.name}
              </p>
              <p className="text-xs text-body-faint mt-0.5">
                {new Date(t.modified * 1000).toLocaleString()}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Transcript content */}
      <div className="flex-1 overflow-auto p-8 bg-surface-ground/50">
        {selected ? (
          loading ? (
            <p className="text-body-faint animate-pulse-warm">Loading...</p>
          ) : (
            <div className="max-w-3xl animate-fade-up" data-printable>
              <div className="flex items-center justify-between mb-5 print-hide">
                <h2 className="text-xl text-body-heading font-display">{selected}</h2>
                <button
                  onClick={() => window.print()}
                  className="text-body-faint hover:text-body-label transition-colors p-1.5 rounded-lg hover:bg-surface-dim"
                  aria-label="Print transcript"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="6 9 6 2 18 2 18 9" />
                    <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                    <rect x="6" y="14" width="12" height="8" />
                  </svg>
                </button>
              </div>
              <div className="bg-surface rounded-xl border border-border p-8 shadow-sm prose max-w-none chat-text">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
              </div>
            </div>
          )
        ) : (
          <div className="text-center text-body-faint mt-24 animate-fade-up">
            <p
              className="text-lg text-body-muted font-display"
            >
              Select a transcript
            </p>
            <p className="text-sm mt-1">to review a past session.</p>
          </div>
        )}
      </div>
    </div>
  );
}
