import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getDocument, getProtocolTree, getPacketStatus } from "../api/client";
import type { DocumentStatus, ProtocolFile } from "../types";
import EmptyState from "./EmptyState";

/** Trigger a print dialog for the main webview.
 *
 * ``window.print()`` is a no-op inside WKWebView (and unreliable on
 * WebView2), so the Tauri shell exposes a ``print_main_window``
 * command that routes the request through ``WebviewWindow::print``
 * Rust-side.  The IPC import is lazy so the browser/dev build (where
 * ``@tauri-apps/api/core`` is unavailable) falls through cleanly to
 * the standard ``window.print()`` path.
 */
async function triggerPrint(): Promise<void> {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("print_main_window");
  } catch {
    window.print();
  }
}

function formatJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

interface FileGroup {
  files: ProtocolFile[];
  subgroups: Map<string, ProtocolFile[]>;
}

function buildGroups(tree: ProtocolFile[]): Map<string, FileGroup> {
  const groups = new Map<string, FileGroup>();

  for (const f of tree) {
    const parts = f.path.split("/");
    if (parts.length <= 2) {
      const dir = parts.length === 1 ? "." : parts[0];
      if (!groups.has(dir)) groups.set(dir, { files: [], subgroups: new Map() });
      groups.get(dir)!.files.push(f);
    } else {
      const topDir = parts[0];
      const subDir = parts.slice(1, -1).join("/");
      if (!groups.has(topDir)) groups.set(topDir, { files: [], subgroups: new Map() });
      const group = groups.get(topDir)!;
      if (!group.subgroups.has(subDir)) group.subgroups.set(subDir, []);
      group.subgroups.get(subDir)!.push(f);
    }
  }

  return groups;
}

const STATUS_COLORS: Record<string, string> = {
  current: "bg-status-ok",
  stale: "bg-status-warn",
  empty: "bg-body-faint",
  missing: "bg-status-error",
  untracked: "bg-status-info",
};

export default function ProtocolViewer() {
  const location = useLocation();
  const navigate = useNavigate();
  const [tree, setTree] = useState<ProtocolFile[]>([]);
  const [exists, setExists] = useState(true);
  const [statuses, setStatuses] = useState<Record<string, DocumentStatus>>({});
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getProtocolTree()
      .then((data) => {
        setExists(data.exists);
        setTree(data.tree);
      })
      .catch(() => {});

    getPacketStatus()
      .then((data) => setStatuses(data.report.documents))
      .catch(() => {});
  }, []);

  const selectFile = useCallback((path: string) => {
    setSelectedPath(path);
    setLoading(true);
    getDocument(path)
      .then((data) => setContent(data.content))
      .catch((err) => setContent(`Error: ${err.message}`))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const target = (location.state as { selectedFile?: string } | null)?.selectedFile;
    if (target && tree.length > 0) {
      const match = tree.find((f) => f.path === target);
      if (match) {
        selectFile(match.path);
      }
    }
  }, [tree, location.state, selectFile]);

  if (!exists) {
    return (
      <div className="flex items-center justify-center h-full">
        <EmptyState
          heading="No protocol yet"
          description="Start a session with the Clarity Agent to create your project's protocol documents."
          actions={[
            {
              label: "Start a session",
              primary: true,
              onClick: () => navigate("/"),
            },
          ]}
        />
      </div>
    );
  }

  const groups = buildGroups(tree);

  const fileButton = (f: ProtocolFile, indent: string) => {
    const status = statuses[f.path]?.status;
    return (
      <button
        key={f.path}
        onClick={() => selectFile(f.path)}
        className={`w-full text-left ${indent} pr-5 py-2 text-sm flex items-center gap-2.5
          transition-all duration-150 ${
            selectedPath === f.path
              ? "bg-accent-surface text-accent-surface-body border-l-2 border-accent -ml-px"
              : "text-body-label hover:bg-surface-dim hover:pl-[calc(var(--pl)+4px)]"
          }`}
        style={{ "--pl": indent === "pl-5" ? "1.25rem" : indent === "pl-9" ? "2.25rem" : "3rem" } as React.CSSProperties}
      >
        {status && (
          <span
            className={`w-1.5 h-1.5 rounded-full shrink-0 ${STATUS_COLORS[status] ?? "bg-disabled"}`}
            title={status}
          />
        )}
        <span className="truncate">{f.name}</span>
      </button>
    );
  };

  return (
    <div className="flex h-full">
      {/* File tree.  ``print-hide`` keeps the document list out of
          the print view — the global print CSS shows ancestors of
          ``[data-printable]`` via ``:has(...)``, but siblings inside
          those ancestors inherit visibility and would otherwise
          leak into the printout. */}
      <div className="w-64 border-r border-border overflow-auto bg-surface print-hide">
        <div className="px-5 py-4 border-b border-border">
          <h2
            className="text-sm text-body-heading font-display"
          >
            .clarity-protocol/
          </h2>
        </div>
        <div className="py-2">
          {Array.from(groups.entries()).map(([dir, group], i) => (
            <div key={dir} className="animate-fade-up" style={{ animationDelay: `${i * 50}ms` }}>
              {dir !== "." && (
                <div className="px-5 py-2 text-[10px] font-medium tracking-widest uppercase text-body-faint">
                  {dir}/
                </div>
              )}
              {group.files.map((f) => fileButton(f, dir === "." ? "pl-5" : "pl-9"))}
              {Array.from(group.subgroups.entries()).map(([subDir, subFiles]) => (
                <div key={`${dir}/${subDir}`}>
                  <div className="pl-9 pr-5 py-1.5 text-[10px] font-medium tracking-widest text-body-faint">
                    {subDir}/
                  </div>
                  {subFiles.map((f) => fileButton(f, "pl-12"))}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Document content */}
      <div className="flex-1 overflow-auto p-8 bg-surface-ground/50">
        {selectedPath ? (
          loading ? (
            <p className="text-body-faint animate-pulse-warm">Loading...</p>
          ) : (
            <div className="max-w-3xl animate-fade-up" data-printable>
              <div className="flex items-center justify-between mb-5">
                <h2
                  className="text-xl text-body-heading font-display"
                >
                  {selectedPath}
                </h2>
                <button
                  onClick={() => void triggerPrint()}
                  className="print-hide text-body-faint hover:text-body-label transition-colors p-1.5 rounded-lg hover:bg-surface-dim"
                  aria-label="Print document"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="6 9 6 2 18 2 18 9" />
                    <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                    <rect x="6" y="14" width="12" height="8" />
                  </svg>
                </button>
              </div>
              <div className="bg-surface rounded-xl border border-border p-8 shadow-sm">
                {selectedPath.endsWith(".json") ? (
                  <pre
                    className="bg-code-bg text-code-text rounded-xl p-5 overflow-x-auto text-sm whitespace-pre font-mono"
                  >
                    {formatJson(content)}
                  </pre>
                ) : (
                  <div className="prose max-w-none chat-text">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          )
        ) : (
          <div className="text-center text-body-faint mt-24 animate-fade-up">
            <p
              className="text-lg text-body-muted font-display"
            >
              Select a document from the tree
            </p>
            <p className="text-sm mt-1">to view its contents.</p>
          </div>
        )}
      </div>
    </div>
  );
}
