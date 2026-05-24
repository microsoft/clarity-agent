import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  activateProject,
  createProject,
  getProjects,
  type CreateProjectResult,
} from "../api/client";
import type { ProjectEntry } from "../types";
import {
  open as tauriOpen,
  save as tauriSave,
} from "@tauri-apps/plugin-dialog";
import { refreshRecentMenu } from "./Layout";

interface ProjectSwitcherProps {
  currentProject: string | undefined;
}

function timeAgo(ts: number): string {
  const seconds = Math.floor(Date.now() / 1000 - ts);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** True when the app is running inside a Tauri desktop wrapper. */
function hasNativeDialogs(): boolean {
  return "__TAURI_INTERNALS__" in window || "__TAURI__" in window;
}

/** Derive a project name from a filesystem path's basename. */
function deriveName(path: string): string {
  return path.split("/").filter(Boolean).pop() || "project";
}

/**
 * Modal state for the flow-3 SetupPromptDialog (open ambiguous /
 * broken directory) and the EmbeddedCommandDialog (user picked
 * embedded — surface the CLI command).  Kept as a discriminated
 * union so the JSX dispatch is exhaustive.
 */
type PromptState =
  | { kind: "needs_setup"; name: string; path: string;
      looks_like_code: boolean;
      suggested_mode: "embedded" | "userspace" }
  | { kind: "broken_install"; name: string; path: string;
      brokenness: string }
  | { kind: "embedded_command"; name: string; path: string;
      command: string }
  | null;

export default function ProjectSwitcher({ currentProject }: ProjectSwitcherProps) {
  const navigate = useNavigate();
  // Auto-expand when no project is active so the list is immediately visible.
  const [open, setOpen] = useState(!currentProject);
  const [projects, setProjects] = useState<ProjectEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [activating, setActivating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // New-project inline form (browser-mode fallback only).
  const [showNewForm, setShowNewForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  // Open-folder fallback form (browser mode only).
  const [showOpenForm, setShowOpenForm] = useState(false);
  const [openPath, setOpenPath] = useState("");

  // Flow-3 prompt — null when no decision is pending.
  const [prompt, setPrompt] = useState<PromptState>(null);
  const [submittingMode, setSubmittingMode] = useState<
    "userspace" | "embedded" | null
  >(null);

  const newInputRef = useRef<HTMLInputElement>(null);
  const openInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    getProjects()
      .then((data) => setProjects(data.projects))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (open) refresh();
  }, [open, refresh]);

  useEffect(() => {
    if (showNewForm) newInputRef.current?.focus();
  }, [showNewForm]);
  useEffect(() => {
    if (showOpenForm) openInputRef.current?.focus();
  }, [showOpenForm]);

  const handleActivate = async (project: ProjectEntry) => {
    setActivating(project.name);
    setError(null);
    try {
      await activateProject(project.name);
      setOpen(false);
      refreshRecentMenu();
      navigate(`/p/${project.id}/`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setActivating(null);
    }
  };

  /**
   * Dispatch on a ``CreateProjectResult`` from the launcher: activate
   * on success, raise the appropriate modal on the 409 / install-required
   * branches.  Centralised so every callsite (initial open, retry-after-
   * SetupPromptDialog, retry-after-EmbeddedCommandDialog) routes the
   * same way.
   */
  const handleCreateResult = async (
    result: CreateProjectResult,
    fallback: { name: string; path: string },
  ) => {
    if (result.status === "ok") {
      setPrompt(null);
      await handleActivate(result.entry);
      return;
    }
    if (result.status === "needs_setup") {
      setPrompt({
        kind: "needs_setup",
        name: fallback.name,
        path: result.path,
        looks_like_code: result.looks_like_code,
        suggested_mode: result.suggested_mode,
      });
      return;
    }
    if (result.status === "broken_install") {
      setPrompt({
        kind: "broken_install",
        name: fallback.name,
        path: result.path,
        brokenness: result.brokenness,
      });
      return;
    }
    if (result.status === "embedded_install_required") {
      setPrompt({
        kind: "embedded_command",
        name: fallback.name,
        path: result.path,
        command: result.command,
      });
      return;
    }
  };

  // ---- Browser-mode fallback (inline form) -------------------------------

  const handleCreateFromForm = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const name = newName.trim();
      const result = await createProject({ name, intent: "create_new" });
      setShowNewForm(false);
      setNewName("");
      await handleCreateResult(result, { name, path: "" });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  };

  // ---- Flow 1: New Project ------------------------------------------------

  const handleNew = async () => {
    setError(null);
    if (!hasNativeDialogs()) {
      setShowNewForm(true);
      setShowOpenForm(false);
      return;
    }
    try {
      // Save-file dialog is the macOS-natural convention for "name a
      // new thing and pick where it goes."  The user types the
      // project name and navigates to a parent location; the
      // returned path is `<parent>/<name>` (doesn't exist yet — the
      // backend mkdirs it as part of setup_userspace_project).
      const path = await tauriSave({
        title: "New Clarity project",
        defaultPath: "Untitled Project",
      });
      if (!path) return; // user cancelled
      const name = deriveName(path);
      const result = await createProject({
        name, path, intent: "create_new",
      });
      setOpen(false);
      await handleCreateResult(result, { name, path });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  // ---- Flows 2 & 3: Open Project -----------------------------------------

  const handleOpenFolder = async () => {
    setError(null);
    if (!hasNativeDialogs()) {
      setShowOpenForm(true);
      return;
    }
    try {
      const path = await tauriOpen({
        directory: true, title: "Open Clarity project",
      });
      if (!path) return;
      const name = deriveName(path);
      // No mode on the initial open — let the backend decide whether
      // this is flow 2 (clean layout → 200 ok) or flow 3 (needs prompt).
      const result = await createProject({
        name, path, intent: "open_existing",
      });
      setOpen(false);
      await handleCreateResult(result, { name, path });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleOpenPath = async () => {
    const path = openPath.trim();
    if (!path) return;
    setError(null);
    const name = deriveName(path);
    try {
      const result = await createProject({
        name, path, intent: "open_existing",
      });
      setShowOpenForm(false);
      setOpenPath("");
      await handleCreateResult(result, { name, path });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  // ---- Flow 3 prompt resolution ------------------------------------------

  const resolveSetup = async (mode: "userspace" | "embedded") => {
    if (!prompt || prompt.kind === "embedded_command") return;
    setSubmittingMode(mode);
    try {
      const result = await createProject({
        name: prompt.name, path: prompt.path,
        intent: "open_existing", mode,
      });
      await handleCreateResult(result, { name: prompt.name, path: prompt.path });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmittingMode(null);
    }
  };

  const retryAfterEmbeddedInstall = async () => {
    if (!prompt || prompt.kind !== "embedded_command") return;
    // The user has (presumably) run the install command in their
    // terminal; re-open without a mode so the backend re-detects
    // — a successful install will now show as clean EMBEDDED.
    try {
      const result = await createProject({
        name: prompt.name, path: prompt.path,
        intent: "open_existing",
      });
      await handleCreateResult(result, { name: prompt.name, path: prompt.path });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const copyCommand = (command: string) => {
    void navigator.clipboard?.writeText(command);
  };

  const cancelForms = () => {
    setShowNewForm(false);
    setNewName("");
    setShowOpenForm(false);
    setOpenPath("");
    setError(null);
  };

  const currentName = currentProject?.split("/").pop() ?? "No project";

  return (
    <div className="border-b border-sidebar-line/20 animate-fade-in">
      {/* Trigger button */}
      <button
        onClick={() => { setOpen(!open); if (open) cancelForms(); }}
        className="w-full flex items-center gap-2.5 px-5 py-3 text-left
          hover:bg-sidebar-active/40 transition-colors duration-150 group"
        title={currentProject}
      >
        <svg className="w-4 h-4 text-sidebar-text-muted shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
        </svg>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-sidebar-text truncate">
            {currentName}
          </p>
        </div>
        <svg
          className={`w-3 h-3 text-sidebar-text-faint shrink-0 transition-transform duration-200 ${
            open ? "rotate-90" : ""
          } group-hover:text-sidebar-text-secondary`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </button>

      {/* Expandable panel */}
      <div className={`overflow-hidden transition-all duration-300 ease-out ${open ? "max-h-[480px] opacity-100" : "max-h-0 opacity-0"}`}>
        <div className="ml-5 border-l border-sidebar-line/40 pb-2">

          {/* Error banner */}
          {error && (
            <div className="pl-4 pr-3 py-1.5 mx-1 mb-1 rounded text-[11px] text-status-error-text bg-status-error-bg">
              {error}
              <button onClick={() => setError(null)} className="ml-1 underline hover:no-underline">dismiss</button>
            </div>
          )}

          {/* Project list */}
          {loading && projects.length === 0 ? (
            <div className="pl-4 pr-5 py-2 text-xs text-sidebar-text-faint">Loading...</div>
          ) : projects.length === 0 ? (
            <div className="pl-4 pr-5 py-2 text-xs text-sidebar-text-faint">No projects yet</div>
          ) : (
            projects.map((project) => {
              const isCurrent = project.path === currentProject;
              return (
                <button
                  key={project.name}
                  onClick={() => !isCurrent && !activating && handleActivate(project)}
                  disabled={isCurrent || activating !== null}
                  title={project.path}
                  className={`w-full text-left flex items-center gap-2 pl-4 pr-3 py-1.5 text-sm
                    transition-all duration-150 disabled:cursor-default ${
                    isCurrent
                      ? "text-sidebar-text bg-sidebar-active/80 border-l-2 border-accent-focus -ml-px"
                      : "text-sidebar-text-muted hover:text-sidebar-text hover:pl-5"
                  }`}
                >
                  <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    project.running
                      ? isCurrent ? "bg-accent-focus" : "bg-status-ok"
                      : "bg-sidebar-line/60"
                  }`} />
                  <span className="truncate flex-1 min-w-0">{project.name}</span>
                  {activating === project.name ? (
                    <svg className="w-3 h-3 animate-spin shrink-0 text-accent" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.3" />
                      <path d="M12 2a10 10 0 019.95 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    </svg>
                  ) : (
                    <span className="text-[10px] text-sidebar-text-faint shrink-0">{timeAgo(project.last_opened)}</span>
                  )}
                </button>
              );
            })
          )}

          {/* Divider */}
          <div className="my-1 mx-3 border-t border-sidebar-line/30" />

          {/* New / Open buttons (or inline forms for browser mode) */}
          {showNewForm ? (
            <div className="pl-4 pr-3 py-1.5 space-y-1.5">
              <input
                ref={newInputRef}
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreateFromForm();
                  if (e.key === "Escape") { setShowNewForm(false); setNewName(""); }
                }}
                placeholder="Project name"
                className="w-full px-2 py-1 text-xs rounded border border-sidebar-line/60
                  bg-sidebar text-sidebar-text placeholder:text-sidebar-text-faint
                  focus:outline-none focus:border-accent/60"
              />
              <div className="flex gap-1.5">
                <button
                  onClick={handleCreateFromForm}
                  disabled={!newName.trim() || creating}
                  className="flex-1 py-1 text-xs rounded bg-accent text-white
                    hover:bg-accent-hover disabled:opacity-50 transition-colors"
                >
                  {creating ? "Creating…" : "Create"}
                </button>
                <button
                  onClick={() => { setShowNewForm(false); setNewName(""); }}
                  className="px-2 py-1 text-xs rounded text-sidebar-text-muted
                    hover:text-sidebar-text hover:bg-sidebar-active/40 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : showOpenForm ? (
            <div className="pl-4 pr-3 py-1.5 space-y-1.5">
              <input
                ref={openInputRef}
                type="text"
                value={openPath}
                onChange={(e) => setOpenPath(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleOpenPath();
                  if (e.key === "Escape") { setShowOpenForm(false); setOpenPath(""); }
                }}
                placeholder="/path/to/project"
                className="w-full px-2 py-1 text-xs rounded border border-sidebar-line/60
                  bg-sidebar text-sidebar-text placeholder:text-sidebar-text-faint
                  font-mono focus:outline-none focus:border-accent/60"
              />
              <div className="flex gap-1.5">
                <button
                  onClick={handleOpenPath}
                  disabled={!openPath.trim()}
                  className="flex-1 py-1 text-xs rounded bg-accent text-white
                    hover:bg-accent-hover disabled:opacity-50 transition-colors"
                >
                  Open
                </button>
                <button
                  onClick={() => { setShowOpenForm(false); setOpenPath(""); }}
                  className="px-2 py-1 text-xs rounded text-sidebar-text-muted
                    hover:text-sidebar-text hover:bg-sidebar-active/40 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex gap-1 pl-3 pr-3 py-0.5">
              <button
                onClick={handleNew}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs rounded
                  text-sidebar-text-muted hover:text-sidebar-text hover:bg-sidebar-active/40
                  transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                New
              </button>
              <button
                onClick={handleOpenFolder}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs rounded
                  text-sidebar-text-muted hover:text-sidebar-text hover:bg-sidebar-active/40
                  transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 9.776c.112-.017.227-.026.344-.026h15.812c.117 0 .232.009.344.026m-16.5 0a2.25 2.25 0 00-1.883 2.542l.857 6a2.25 2.25 0 002.227 1.932H19.05a2.25 2.25 0 002.227-1.932l.857-6a2.25 2.25 0 00-1.883-2.542m-16.5 0V6A2.25 2.25 0 016 3.75h3.879a1.5 1.5 0 011.06.44l2.122 2.12a1.5 1.5 0 001.06.44H18A2.25 2.25 0 0120.25 9v.776" />
                </svg>
                Open
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Flow-3 SetupPromptDialog (needs_setup / broken_install) and
          the EmbeddedCommandDialog all render as fixed-position
          modal overlays so they sit above the sidebar UI without
          fighting its layout. */}
      {prompt && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center
            bg-black/40 animate-fade-in"
          onClick={() => setPrompt(null)}
        >
          <div
            className="max-w-md w-full mx-4 rounded-xl bg-surface
              border border-border shadow-xl p-5"
            onClick={(e) => e.stopPropagation()}
          >
            {prompt.kind === "needs_setup" && (
              <>
                <h3 className="text-sm font-medium text-body mb-2">
                  Set up Clarity here?
                </h3>
                <p className="text-xs text-body-muted mb-1 font-mono break-all">
                  {prompt.path}
                </p>
                <p className="text-xs text-body-muted mb-4">
                  This directory doesn't have a Clarity setup yet.
                  {prompt.looks_like_code
                    ? " It looks like a code repository — an embedded install (with the agent inside the repo) is the natural fit."
                    : " A userspace project will create a Clarity Protocol/ folder here and manage Clarity from the app."}
                </p>
                <div className="space-y-2">
                  {prompt.looks_like_code && (
                    <button
                      disabled={submittingMode !== null}
                      onClick={() => resolveSetup("embedded")}
                      className="w-full py-2 text-xs rounded bg-accent text-white
                        hover:bg-accent-hover disabled:opacity-50 transition-colors"
                    >
                      {submittingMode === "embedded"
                        ? "Working…"
                        : "Set up as embedded install (recommended)"}
                    </button>
                  )}
                  <button
                    disabled={submittingMode !== null}
                    onClick={() => resolveSetup("userspace")}
                    className={`w-full py-2 text-xs rounded transition-colors
                      disabled:opacity-50 ${
                        prompt.looks_like_code
                          ? "border border-border text-body hover:bg-surface-hover"
                          : "bg-accent text-white hover:bg-accent-hover"
                      }`}
                  >
                    {submittingMode === "userspace"
                      ? "Working…"
                      : "Set up as userspace project"}
                  </button>
                  <button
                    onClick={() => setPrompt(null)}
                    className="w-full py-2 text-xs rounded text-body-muted
                      hover:text-body hover:bg-surface-hover transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </>
            )}

            {prompt.kind === "broken_install" && (
              <>
                <h3 className="text-sm font-medium text-body mb-2">
                  Inconsistent Clarity setup
                </h3>
                <p className="text-xs text-body-muted mb-1 font-mono break-all">
                  {prompt.path}
                </p>
                <p className="text-xs text-body-muted mb-4">
                  {prompt.brokenness === "ambiguous_protocol_dirs"
                    ? "Both .clarity-protocol/ and Clarity Protocol/ are present. Please remove one before reopening."
                    : "Found a partial embedded install (.clarity-agent/ or .clarity-protocol/ but not both). Either complete the install with `clarity install --embedded`, or remove the stray directory and reopen as a userspace project."}
                </p>
                <button
                  onClick={() => setPrompt(null)}
                  className="w-full py-2 text-xs rounded bg-accent text-white
                    hover:bg-accent-hover transition-colors"
                >
                  OK
                </button>
              </>
            )}

            {prompt.kind === "embedded_command" && (
              <>
                <h3 className="text-sm font-medium text-body mb-2">
                  Run this in your terminal
                </h3>
                <p className="text-xs text-body-muted mb-3">
                  Embedded installs require the CLI (it clones the agent
                  into the repo and sets up a venv).  Run the command
                  below, then click <em>Try again</em> to open the project.
                </p>
                <div className="flex gap-2 mb-4">
                  <code className="flex-1 px-2 py-2 text-[11px] rounded
                    bg-surface-inset text-body font-mono break-all">
                    {prompt.command}
                  </code>
                  <button
                    onClick={() => copyCommand(prompt.command)}
                    title="Copy"
                    className="px-3 text-xs rounded border border-border
                      text-body hover:bg-surface-hover transition-colors"
                  >
                    Copy
                  </button>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={retryAfterEmbeddedInstall}
                    className="flex-1 py-2 text-xs rounded bg-accent text-white
                      hover:bg-accent-hover transition-colors"
                  >
                    Try again
                  </button>
                  <button
                    onClick={() => setPrompt(null)}
                    className="px-3 py-2 text-xs rounded text-body-muted
                      hover:text-body hover:bg-surface-hover transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
