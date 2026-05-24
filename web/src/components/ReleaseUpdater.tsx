/**
 * Release-binary auto-updater UI.
 *
 * Runs only when ``/api/version`` reports ``source === "release"``
 * (i.e. a packaged Tauri build).  Talks to the Rust side via the
 * ``check_for_update`` / ``download_and_install_update`` /
 * ``restart_app`` commands defined in ``src-tauri/src/main.rs``;
 * those wrap ``tauri-plugin-updater`` and honor the
 * ``PRETEND_TO_BE_VERSION`` env var for manual E2E testing.
 *
 * Source-build updates (git checkout, locally-built binary) stay
 * on the existing ``UpdateBadge`` flow in ``Sidebar.tsx`` — that
 * one shells out to ``git pull``, which is fundamentally different
 * and would be confusing to merge with the signed-binary path.
 */
import { useCallback, useEffect, useState } from "react";

const POLL_INTERVAL_MS = 60 * 60 * 1000; // hourly per #48

type Phase = "idle" | "available" | "downloading" | "ready" | "error";

interface UpdateCheckResult {
  available: boolean;
  version: string | null;
  notes: string | null;
}

function isTauri(): boolean {
  return (
    typeof window !== "undefined" &&
    ("__TAURI_INTERNALS__" in window || "__TAURI__" in window)
  );
}

/**
 * Wraps the lazy ``@tauri-apps/api/core`` import so the bundled
 * module isn't pulled into the chunk when we're not in Tauri (the
 * caller short-circuits on ``isTauri()`` first).
 */
async function invokeTauri<T>(cmd: string): Promise<T> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<T>(cmd);
}

export default function ReleaseUpdater({ collapsed }: { collapsed: boolean }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [version, setVersion] = useState<string | null>(null);
  const [notes, setNotes] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);

  const check = useCallback(async () => {
    if (!isTauri()) return;
    try {
      const res = await invokeTauri<UpdateCheckResult>("check_for_update");
      if (res.available && res.version) {
        // Only flip the phase if we haven't already moved past
        // ``available`` — re-polling shouldn't reset a user who
        // already clicked "Install" mid-download.
        setPhase((cur) => (cur === "downloading" || cur === "ready" ? cur : "available"));
        setVersion(res.version);
        setNotes(res.notes);
      }
    } catch (e) {
      // Network blip / endpoint down → silent.  This polls hourly;
      // a tooltip on every transient failure would be noisy.  The
      // VersionLabel still shows the running version via the
      // separate /api/version endpoint, which has its own UI.
      void e;
    }
  }, []);

  useEffect(() => {
    void check();
    const id = setInterval(() => void check(), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [check]);

  const handleInstall = async () => {
    setPhase("downloading");
    setError(null);
    try {
      await invokeTauri<void>("download_and_install_update");
      setPhase("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("error");
    }
  };

  const handleRestart = async () => {
    try {
      await invokeTauri<void>("restart_app");
    } catch (e) {
      // ``restart`` may resolve after the new process kills the old
      // one, in which case we never see the resolution.  Treat
      // anything that does come back as an error.
      setError(e instanceof Error ? e.message : String(e));
      setPhase("error");
    }
  };

  if (phase === "idle") return null;

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
        {showModal && renderModal()}
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
        title={`Update to ${version ?? "the latest version"}`}
      >
        <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
        </svg>
        <span>
          Update available
          {version && (
            <span className="text-accent-focus/70 font-normal">
              {" "}&middot; {version}
            </span>
          )}
        </span>
      </button>
      {showModal && renderModal()}
    </>
  );

  function renderModal() {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
        <div className="bg-surface rounded-xl shadow-2xl w-full max-w-md mx-4 p-6 text-body">
          <h2 className="text-lg font-display mb-4">Update Clarity</h2>

          {phase === "available" && (
            <>
              <p className="text-sm text-body-muted mb-2">
                Clarity {version} is available.  Click Install to download
                and apply the update; you'll be prompted to restart
                when it's ready.
              </p>
              {notes && (
                <pre className="text-xs text-body-muted bg-surface-dim rounded-lg p-3 mb-4 max-h-40 overflow-auto whitespace-pre-wrap font-sans">
                  {notes}
                </pre>
              )}
            </>
          )}

          {phase === "downloading" && (
            <div className="flex items-center gap-3 text-sm text-body-muted mb-4">
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.3" />
                <path d="M12 2a10 10 0 019.95 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
              Downloading and verifying the update...
            </div>
          )}

          {phase === "ready" && (
            <p className="text-sm text-body-muted mb-4">
              The update is installed.  Restart Clarity to start running {version}.
            </p>
          )}

          {error && (
            <p className="text-sm text-status-error-text bg-status-error-bg rounded-lg px-3 py-2 mb-4">
              Error: {error}
            </p>
          )}

          <div className="flex justify-end gap-3">
            {phase !== "downloading" && (
              <button
                onClick={() => {
                  setShowModal(false);
                  if (phase === "error") setPhase("available");
                }}
                className="px-4 py-2 text-sm rounded-lg text-body-muted
                  hover:text-body hover:bg-surface-dim transition-colors"
              >
                Later
              </button>
            )}
            {phase === "available" && (
              <button
                onClick={handleInstall}
                className="px-4 py-2 text-sm rounded-lg bg-accent-focus text-white
                  hover:brightness-110 transition-all"
              >
                Install
              </button>
            )}
            {phase === "error" && (
              <button
                onClick={handleInstall}
                className="px-4 py-2 text-sm rounded-lg bg-accent-focus text-white
                  hover:brightness-110 transition-all"
              >
                Try again
              </button>
            )}
            {phase === "ready" && (
              <button
                onClick={handleRestart}
                className="px-4 py-2 text-sm rounded-lg bg-accent-focus text-white
                  hover:brightness-110 transition-all"
              >
                Restart Now
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }
}
