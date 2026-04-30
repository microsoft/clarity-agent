import { useEffect, useState, useCallback } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { getSession, checkForUpdate, runUpdate, restartServer } from "../api/client";
import type { SessionInfo, UpdateRunResult } from "../types";
import GlossaryTerm from "./GlossaryTerm";
import ModelSelector from "./ModelSelector";
import ProjectSwitcher from "./ProjectSwitcher";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  launcherMode?: boolean;
  projectId?: string;
  noActiveProject?: boolean;
  onShowSetup?: () => void;
  onShowFeedback?: () => void;
}

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
  icon: React.ReactNode;
  /** If set, wraps the label in a GlossaryTerm tooltip. */
  glossary?: string;
}

interface NavGroup {
  label: string;
  basePaths: string[];
  children: NavItem[];
}

/* Simple SVG icons — small, inline */
const ChatIcon = () => (
  <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
  </svg>
);

const HistoryIcon = () => (
  <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const DocIcon = () => (
  <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
  </svg>
);

const PacketIcon = () => (
  <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
  </svg>
);

const StatusIcon = () => (
  <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605" />
  </svg>
);

/** Build nav groups with an optional project-scoped prefix (e.g. "/p/abc123"). */
function buildNavGroups(prefix: string): NavGroup[] {
  const p = prefix; // shorthand
  return [
    {
      label: "Chat",
      basePaths: [`${p}/`, `${p}/history`],
      children: [
        { to: `${p}/`, label: "Session", end: true, icon: <ChatIcon /> },
        { to: `${p}/history`, label: "History", icon: <HistoryIcon /> },
      ],
    },
    {
      label: "Protocol",
      basePaths: [`${p}/protocol`, `${p}/packet`, `${p}/packet-status`],
      children: [
        { to: `${p}/protocol`, label: "Documents", icon: <DocIcon />, glossary: "Documents" },
        { to: `${p}/packet`, label: "Review Packet", icon: <PacketIcon />, glossary: "Review Packet" },
        { to: `${p}/packet-status`, label: "Status", icon: <StatusIcon />, glossary: "Status" },
      ],
    },
  ];
}

function NavGroupItem({
  group,
  index,
  collapsed,
}: {
  group: NavGroup;
  index: number;
  collapsed: boolean;
}) {
  const location = useLocation();
  const isGroupActive = group.basePaths.some((p) =>
    p.endsWith("/")
      ? location.pathname === p || location.pathname === p.slice(0, -1)
      : location.pathname.startsWith(p),
  );
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    if (isGroupActive) setExpanded(true);
  }, [isGroupActive]);

  if (collapsed) {
    // In collapsed mode, show icons only
    return (
      <div className="animate-fade-in px-2 space-y-0.5">
        {group.children.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            title={item.label}
            className={({ isActive }) =>
              `flex items-center justify-center w-10 h-10 rounded-lg mx-auto transition-all duration-150 ${
                isActive
                  ? "bg-sidebar-active text-sidebar-text"
                  : "text-sidebar-text-muted hover:bg-sidebar-active/60 hover:text-sidebar-text"
              }`
            }
          >
            {item.icon}
          </NavLink>
        ))}
      </div>
    );
  }

  return (
    <div
      className="animate-fade-up"
      style={{ animationDelay: `${100 + index * 75}ms` }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        className={`w-full flex items-center justify-between px-5 py-2.5 text-xs tracking-widest uppercase transition-all duration-200 ${
          isGroupActive
            ? "text-sidebar-text font-medium"
            : "text-sidebar-text-muted hover:text-sidebar-text-secondary"
        }`}
      >
        <span>{group.label}</span>
        <svg
          className={`w-3 h-3 transition-transform duration-200 ${expanded ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </button>

      <div
        className={`overflow-hidden transition-all duration-300 ease-out ${
          expanded ? "max-h-48 opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="ml-5 border-l border-sidebar-line/40 pb-1">
          {group.children.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 pl-4 pr-5 py-1.5 text-sm transition-all duration-150 ${
                  isActive
                    ? "text-sidebar-text bg-sidebar-active/80 border-l-2 border-accent-focus -ml-px"
                    : "text-sidebar-text-muted hover:text-sidebar-text hover:pl-5"
                }`
              }
            >
              {item.icon}
              <span>
                {item.glossary
                  ? <GlossaryTerm term={item.glossary}>{item.label}</GlossaryTerm>
                  : item.label}
              </span>
            </NavLink>
          ))}
        </div>
      </div>
    </div>
  );
}

const UPDATE_CHECK_INTERVAL_MS = 30 * 60 * 1000; // 30 minutes

function UpdateBadge({ collapsed }: { collapsed: boolean }) {
  const [available, setAvailable] = useState(false);
  const [commitCount, setCommitCount] = useState(0);
  const [frozen, setFrozen] = useState(false);
  const [latestVersion, setLatestVersion] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [result, setResult] = useState<UpdateRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const check = useCallback(() => {
    checkForUpdate()
      .then((info) => {
        setAvailable(info.update_available);
        setCommitCount(info.commit_count);
        setFrozen(info.frozen);
        setLatestVersion(info.latest_version);
        setDownloadUrl(info.download_url);
      })
      .catch(() => {}); // silent — network may be unavailable
  }, []);

  useEffect(() => {
    check();
    const id = setInterval(check, UPDATE_CHECK_INTERVAL_MS);
    return () => clearInterval(id);
  }, [check]);

  const handleUpdate = async () => {
    setUpdating(true);
    setError(null);
    setResult(null);
    try {
      const res = await runUpdate();
      setResult(res);
      if (res.success) setAvailable(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUpdating(false);
    }
  };

  const handleRestart = async () => {
    setRestarting(true);
    setError(null);
    try {
      await restartServer();
    } catch {
      // Expected — the server dies before responding in some cases
    }
    // Poll until the server comes back, then reload the page.
    const deadline = Date.now() + 30_000;
    const poll = async () => {
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 2000));
        try {
          const resp = await fetch("/api/session", { signal: AbortSignal.timeout(3000) });
          if (resp.ok) {
            window.location.reload();
            return;
          }
        } catch {
          // Server still restarting
        }
      }
      setRestarting(false);
      setError("Server did not come back within 30 seconds. You may need to restart manually.");
    };
    poll();
  };

  if (!available && !showModal) return null;

  if (collapsed) {
    return (
      <div className="flex justify-center py-2">
        <button
          onClick={() => setShowModal(true)}
          className="w-6 h-6 rounded-md bg-accent-focus/20 flex items-center justify-center hover:bg-accent-focus/30 transition-colors"
          aria-label="Update available"
        >
          <svg className="w-3.5 h-3.5 text-accent-focus" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        className="mx-3 mt-3 mb-2 flex items-center gap-2.5 px-3 py-2 rounded-lg
          bg-accent-focus/15 text-accent-focus text-xs font-medium
          hover:bg-accent-focus/25 transition-colors duration-150
          border border-accent-focus/20"
        title="Click to update"
      >
        <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
        </svg>
        <span>
          Update available
          {frozen && latestVersion && (
            <span className="text-accent-focus/70 font-normal">
              {" "}&middot; v{latestVersion}
            </span>
          )}
          {!frozen && commitCount > 0 && (
            <span className="text-accent-focus/70 font-normal">
              {" "}&middot; {commitCount} commit{commitCount !== 1 ? "s" : ""}
            </span>
          )}
        </span>
      </button>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-surface rounded-xl shadow-2xl w-full max-w-md mx-4 p-6 text-body">
            <h2 className="text-lg font-display mb-4">Update Clarity</h2>

            {frozen ? (
              /* Frozen (desktop app) mode: can't update in-place, link to download */
              <>
                <p className="text-sm text-body-muted mb-4">
                  Clarity v{latestVersion} is available.
                  Download the new version to update.
                </p>
                <div className="flex justify-end gap-3">
                  <button
                    onClick={() => setShowModal(false)}
                    className="px-4 py-2 text-sm rounded-lg text-body-muted
                      hover:text-body hover:bg-surface-dim transition-colors"
                  >
                    Later
                  </button>
                  {downloadUrl && (
                    <a
                      href={downloadUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2 text-sm rounded-lg bg-accent-focus text-white
                        hover:brightness-110 transition-all inline-block"
                    >
                      Download
                    </a>
                  )}
                </div>
              </>
            ) : (
              /* Dev (git checkout) mode: update in-place */
              <>
                {!result && !error && !updating && (
                  <p className="text-sm text-body-muted mb-4">
                    A new version is available. This will pull the latest code,
                    reinstall dependencies, and rebuild the web frontend.
                    You'll need to restart the server afterward.
                  </p>
                )}

                {(updating || restarting) && (
                  <div className="flex items-center gap-3 text-sm text-body-muted mb-4">
                    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.3" />
                      <path d="M12 2a10 10 0 019.95 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    </svg>
                    {restarting ? "Restarting... the page will reload automatically." : "Updating... this may take a minute."}
                  </div>
                )}

                {result && !restarting && (
                  <div className="mb-4 space-y-1">
                    {result.steps.map((step, i) => (
                      <div
                        key={i}
                        className={`text-xs font-mono px-2 py-1 rounded ${
                          step.outcome === "ok"
                            ? "text-status-ok-text bg-status-ok-bg"
                            : step.outcome === "fail"
                              ? "text-status-error-text bg-status-error-bg"
                              : step.outcome === "warn"
                                ? "text-status-warn-text bg-status-warn-bg"
                                : "text-body-muted"
                        }`}
                      >
                        {step.outcome === "ok" ? "\u2713" : step.outcome === "fail" ? "\u2717" : "\u26a0"}{" "}
                        {step.message}
                      </div>
                    ))}
                  </div>
                )}

                {error && (
                  <p className="text-sm text-status-error-text bg-status-error-bg rounded-lg px-3 py-2 mb-4">Error: {error}</p>
                )}

                <div className="flex justify-end gap-3">
                  {!restarting && (
                    <button
                      onClick={() => {
                        setShowModal(false);
                        setResult(null);
                        setError(null);
                      }}
                      className="px-4 py-2 text-sm rounded-lg text-body-muted
                        hover:text-body hover:bg-surface-dim transition-colors"
                    >
                      {result?.success ? "Later" : "Cancel"}
                    </button>
                  )}
                  {!result?.success && !restarting && (
                    <button
                      onClick={handleUpdate}
                      disabled={updating}
                      className="px-4 py-2 text-sm rounded-lg bg-accent-focus text-white
                        hover:brightness-110 disabled:opacity-50 transition-all"
                    >
                      {updating ? "Updating..." : "Update Now"}
                    </button>
                  )}
                  {result?.success && !restarting && (
                    <button
                      onClick={handleRestart}
                      className="px-4 py-2 text-sm rounded-lg bg-accent-focus text-white
                        hover:brightness-110 transition-all"
                    >
                      Restart Now
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

export default function Sidebar({ collapsed, onToggle, launcherMode, projectId, noActiveProject, onShowSetup, onShowFeedback }: SidebarProps) {
  const navPrefix = projectId ? `/p/${projectId}` : "";
  const navGroups = buildNavGroups(navPrefix);
  const [session, setSession] = useState<SessionInfo | null>(null);

  useEffect(() => {
    getSession().then(setSession).catch(() => {});
  }, []);

  return (
    <aside
      className={`print-hide bg-sidebar text-sidebar-text font-sidebar flex flex-col shrink-0 shadow-2xl shadow-black/20
        transition-all duration-300 ease-out ${
          collapsed ? "w-14" : "w-60"
        }`}
    >
      {/* Brand mark + collapse toggle */}
      <div className="px-3 py-4 border-b border-sidebar-line/30 flex items-center justify-between">
        {!collapsed && (
          <div className="animate-fade-in pl-2">
            <h1
              className="text-xl tracking-tight font-display"
            >
              Clarity
            </h1>
            <p className="text-[10px] tracking-[0.2em] uppercase text-sidebar-text-faint mt-0.5">
              Thinking Agent
            </p>
          </div>
        )}
        <button
          onClick={onToggle}
          className={`flex items-center justify-center w-8 h-8 rounded-lg
            text-sidebar-text-faint hover:text-sidebar-text hover:bg-sidebar-active/60
            transition-all duration-200 ${collapsed ? "mx-auto" : ""}`}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <svg
            className={`w-4 h-4 transition-transform duration-300 ${collapsed ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M18.75 19.5l-7.5-7.5 7.5-7.5m-6 15L5.25 12l7.5-7.5" />
          </svg>
        </button>
      </div>

      {/* Update indicator — prominent, near the top */}
      <UpdateBadge collapsed={collapsed} />

      {/* Project indicator / switcher */}
      {session && !collapsed && (
        launcherMode ? (
          <ProjectSwitcher currentProject={session.project_dir} />
        ) : (
          <div
            className="px-5 py-2.5 border-b border-sidebar-line/20 animate-fade-in"
            title={session.project_dir}
          >
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-accent-focus animate-pulse-warm" />
              <p className="text-xs text-sidebar-text-secondary truncate">
                {session.project_dir?.split("/").pop() ?? "No project"}
              </p>
            </div>
          </div>
        )
      )}

      {/* Navigation */}
      <nav className={`flex-1 ${collapsed ? "py-3 space-y-2" : "py-4 space-y-1"}`}>
        {navGroups.map((group, i) => (
          <NavGroupItem
            key={group.label}
            group={group}
            index={i}
            collapsed={collapsed}
          />
        ))}
      </nav>

      {/* Bottom row: model selector + feedback + settings gear */}
      {session && (
        <div className={`flex items-center ${collapsed ? "justify-center py-3" : "gap-1"}`}>
          {!collapsed && !noActiveProject && <div className="flex-1"><ModelSelector /></div>}
          {onShowFeedback && (
            <button
              onClick={onShowFeedback}
              aria-label="Send feedback"
              className={`shrink-0 flex items-center justify-center rounded-lg
                text-sidebar-text-faint hover:text-sidebar-text hover:bg-sidebar-active/60
                transition-all duration-200 ${collapsed ? "w-10 h-10" : "w-8 h-8 mb-1"}`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z" />
              </svg>
            </button>
          )}
          {onShowSetup && (
            <button
              onClick={onShowSetup}
              aria-label="AI provider settings"
              className={`shrink-0 flex items-center justify-center rounded-lg
                text-sidebar-text-faint hover:text-sidebar-text hover:bg-sidebar-active/60
                transition-all duration-200 ${collapsed ? "w-10 h-10" : "w-8 h-8 mr-2 mb-1"}`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
              </svg>
            </button>
          )}
        </div>
      )}
    </aside>
  );
}
