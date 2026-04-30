import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { activateProject, createProject, getProjects } from "../api/client";
import type { ProjectEntry } from "../types";
import { open as tauriOpen } from "@tauri-apps/plugin-dialog";
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

export default function ProjectSwitcher({ currentProject }: ProjectSwitcherProps) {
  const navigate = useNavigate();
  // Auto-expand when no project is active so the list is immediately visible.
  const [open, setOpen] = useState(!currentProject);
  const [projects, setProjects] = useState<ProjectEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [activating, setActivating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // New-project inline form
  const [showNewForm, setShowNewForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  // Open-folder fallback form (shown only in browser mode, not Tauri)
  const [showOpenForm, setShowOpenForm] = useState(false);
  const [openPath, setOpenPath] = useState("");

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

  // Focus the name input when the form appears
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

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const entry = await createProject(newName.trim());
      setShowNewForm(false);
      setNewName("");
      await handleActivate(entry);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  };

  const handleNew = async () => {
    setError(null);
    if (hasNativeDialogs()) {
      try {
        const path = await tauriOpen({ directory: true, title: "Create project folder" });
        if (!path) return;
        const name = path.split("/").filter(Boolean).pop() || "project";
        const entry = await createProject(name, path);
        setOpen(false);
        await handleActivate(entry);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    } else {
      setShowNewForm(true);
      setShowOpenForm(false);
    }
  };

  const handleOpenFolder = async () => {
    setError(null);
    if (hasNativeDialogs()) {
      try {
        const path = await tauriOpen({ directory: true, title: "Open existing project" });
        if (!path) return; // user cancelled
        const name = path.split("/").filter(Boolean).pop() || "project";
        const entry = await createProject(name, path);
        setOpen(false);
        await handleActivate(entry);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    } else {
      setShowOpenForm(true);
    }
  };

  const handleOpenPath = async () => {
    const path = openPath.trim();
    if (!path) return;
    setError(null);
    const name = path.split("/").filter(Boolean).pop() || "project";
    try {
      const entry = await createProject(name, path);
      setShowOpenForm(false);
      setOpenPath("");
      await handleActivate(entry);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
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

          {/* New project form or button */}
          {showNewForm ? (
            <div className="pl-4 pr-3 py-1.5 space-y-1.5">
              <input
                ref={newInputRef}
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreate();
                  if (e.key === "Escape") { setShowNewForm(false); setNewName(""); }
                }}
                placeholder="Project name"
                className="w-full px-2 py-1 text-xs rounded border border-sidebar-line/60
                  bg-sidebar text-sidebar-text placeholder:text-sidebar-text-faint
                  focus:outline-none focus:border-accent/60"
              />
              <div className="flex gap-1.5">
                <button
                  onClick={handleCreate}
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
                onClick={() => { setShowOpenForm(false); handleOpenFolder(); }}
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
    </div>
  );
}
