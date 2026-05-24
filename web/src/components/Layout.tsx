import { useCallback, useEffect, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { activateProject, activateProjectById, createProject, getProjects, removeProject, getSession, getSettings, getSetupStatus } from "../api/client";
import { ChatProvider } from "../hooks/useChat";
import type { SessionInfo } from "../types";
import FeedbackDialog from "./FeedbackDialog";
import PreferencesPanel from "./PreferencesPanel";
import SetupWizard from "./SetupWizard";
import Sidebar from "./Sidebar";
import LoadingScreen from "./LoadingScreen";
import TabTitle from "./TabTitle";

/** Ask the Tauri shell to rebuild the Open Recent submenu.
 *
 * Calls the Python backend which re-writes projects.json; the Rust
 * side re-reads it on next menu open.  We also try the Tauri invoke
 * path in case the IPC bridge is available, but don't depend on it.
 */
export async function refreshRecentMenu(): Promise<void> {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("refresh_recent_menu");
  } catch {
    // IPC bridge not available (remote URL) — menu will refresh on
    // next app restart.  Acceptable degradation.
  }
}


/** Extract the project ID from a /p/:projectId/... URL, or undefined. */
function useProjectId(): string | undefined {
  const params = useParams<{ projectId?: string }>();
  return params.projectId;
}

export default function Layout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [setupNeeded, setSetupNeeded] = useState<boolean | null>(null);
  const [showSetup, setShowSetup] = useState(false);
  const [showPreferences, setShowPreferences] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();
  const projectId = useProjectId();
  const activatingRef = useRef<string | null>(null);

  const fetchSession = useCallback(() => {
    getSession().then((s) => {
      setSession(s);
      setSessionLoading(false);
      if (s.theme) {
        document.documentElement.setAttribute("data-theme", s.theme);
      }
    }).catch(() => {
      setSession(null);
      setSessionLoading(false);
    });
  }, []);

  // Re-fetch session on every route change.
  useEffect(() => {
    fetchSession();
  }, [location.pathname, fetchSession]);

  // When the URL contains a project ID that doesn't match the active
  // project, activate it server-side.  This handles bookmarked URLs and
  // project switching via the sidebar.
  useEffect(() => {
    if (
      !projectId ||
      !session ||
      session.project_id === projectId ||
      activatingRef.current === projectId
    ) {
      return;
    }
    activatingRef.current = projectId;
    setSessionLoading(true);
    activateProjectById(projectId)
      .then(() => fetchSession())
      .catch(() => {
        // Project ID doesn't exist — go to root
        navigate("/", { replace: true });
      })
      .finally(() => {
        activatingRef.current = null;
      });
  }, [projectId, session, fetchSession, navigate]);


  // Listen for native menu events from the Tauri shell.
  //
  // The webview loads from a remote URL (http://localhost:PORT), so the
  // Tauri IPC bridge / event system is NOT injected into the page.
  // The Rust side dispatches CustomEvents via webview.eval() instead,
  // and we listen with standard DOM addEventListener — no Tauri JS API needed.
  useEffect(() => {
    /** Helper: open a path as a project (create or open, activate, navigate).
     *
     * Called from the Tauri menu's "Open Project…" and "New
     * Project…" items.  The Tauri-side handlers already picked a
     * folder, so we just route to the launcher endpoint with the
     * appropriate intent; on the no-layout / broken-install branches
     * we fall through silently rather than popping a dialog — the
     * full flow-3 prompt lives in ``ProjectSwitcher`` and only fires
     * when the user goes through the in-app New/Open buttons.
     */
    const openProjectPath = async (
      path: string, intent: "create_new" | "open_existing",
    ) => {
      const name = path.split("/").filter(Boolean).pop() || "project";
      let id: string;
      try {
        const result = await createProject({ name, path, intent });
        if (result.status === "ok") {
          await activateProject(result.entry.name);
          id = result.entry.id;
        } else {
          // Menu-driven open hit a needs_setup / broken / embedded-
          // required branch; the menu UI has no place to host the
          // SetupPromptDialog, so the user has to use the in-app
          // ProjectSwitcher flow.  Surface nothing; the directory
          // simply doesn't activate.
          return;
        }
      } catch {
        const data = await getProjects();
        const existing = data.projects.find((p) => p.path === path);
        if (!existing) return;
        await activateProject(existing.name);
        id = existing.id;
      }
      await refreshRecentMenu();
      navigate(`/p/${id}/`);
    };

    const onOpen = (e: Event) =>
      openProjectPath((e as CustomEvent).detail, "open_existing");
    const onNew = (e: Event) =>
      openProjectPath((e as CustomEvent).detail, "create_new");
    const onActivate = async (e: Event) => {
      const projectId = (e as CustomEvent).detail;
      await activateProjectById(projectId);
      await refreshRecentMenu();
      navigate(`/p/${projectId}/`);
    };
    // Print is handled natively by Tauri (WebviewWindow::print()),
    // not via JS — window.print() is a no-op in WKWebView.
    const onClearRecent = async () => {
      try {
        const data = await getProjects();
        for (const p of data.projects) {
          await removeProject(p.name);
        }
        await refreshRecentMenu();
      } catch {
        // Best-effort.
      }
    };

    window.addEventListener("clarity-open-project", onOpen);
    window.addEventListener("clarity-new-project", onNew);
    window.addEventListener("clarity-activate-project", onActivate);
    window.addEventListener("clarity-clear-recent", onClearRecent);

    return () => {
      window.removeEventListener("clarity-open-project", onOpen);
      window.removeEventListener("clarity-new-project", onNew);
      window.removeEventListener("clarity-activate-project", onActivate);

      window.removeEventListener("clarity-clear-recent", onClearRecent);
    };
  }, [navigate]);

  // Re-fetch session when the tab regains visibility (catches server restarts).
  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === "visible") fetchSession();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [fetchSession]);

  // Poll session while disconnected so we recover when the server comes back.
  useEffect(() => {
    if (session) return;
    const id = setInterval(fetchSession, 5000);
    return () => clearInterval(id);
  }, [session, fetchSession]);

  // Setup status only needs checking once on mount.
  useEffect(() => {
    getSetupStatus()
      .then((status) => setSetupNeeded(!status.configured))
      .catch(() => setSetupNeeded(false));
  }, []);

  // Apply accessibility settings on mount.
  useEffect(() => {
    getSettings().then((s) => {
      document.documentElement.style.setProperty(
        "--font-scale", String((s.font_scale ?? 100) / 100),
      );
      document.documentElement.setAttribute(
        "data-reduce-motion", s.reduce_motion ?? "system",
      );
    }).catch(() => {});
  }, []);


  // Show loading screen while checking setup status
  if (setupNeeded === null) {
    return <LoadingScreen />;
  }

  // Show setup wizard if no provider is configured, or if manually requested
  if (setupNeeded || showSetup) {
    return <SetupWizard
      onComplete={() => { window.location.reload(); }}
      onCancel={showSetup && !setupNeeded ? () => setShowSetup(false) : undefined}
    />;
  }

  // Loading state while waiting for session after project activation
  if (sessionLoading) {
    return <LoadingScreen />;
  }

  // Session not yet loaded
  if (!session) {
    return <LoadingScreen />;
  }

  const noActiveProject = session.launcher_mode && !session.active;

  const content = (
    <div className="flex h-screen bg-surface-ground">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-[60] focus:top-2 focus:left-2
          focus:px-4 focus:py-2 focus:bg-accent-focus focus:text-white focus:rounded-lg
          focus:text-sm focus:font-medium"
      >
        Skip to content
      </a>
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        launcherMode={session?.launcher_mode}
        projectId={session?.project_id}
        noActiveProject={noActiveProject}
        onShowSetup={() => {
          if (setupNeeded) {
            setShowSetup(true);
          } else {
            setShowPreferences(true);
          }
        }}
        // Feedback UI is hidden for the OSS release; the backend
        // infrastructure (API, dialog component, Azure Function) is
        // kept in place so we can re-enable it later by restoring
        // `onShowFeedback={() => setShowFeedback(true)}`.
      />
      <main id="main-content" className="flex-1 overflow-auto animate-fade-in">
        {noActiveProject ? (
          <div className="h-full flex items-center justify-center text-body-faint text-sm select-none">
            Select or create a project to get started.
          </div>
        ) : (
          <Outlet />
        )}
      </main>
      {showPreferences && (
        <PreferencesPanel onClose={() => setShowPreferences(false)} />
      )}
      {showFeedback && (
        <FeedbackDialog onClose={() => setShowFeedback(false)} />
      )}
    </div>
  );

  // Only mount ChatProvider (and its WebSocket) when a project is active.
  if (noActiveProject) return content;
  return (
    <ChatProvider>
      <TabTitle />
      {content}
    </ChatProvider>
  );
}
