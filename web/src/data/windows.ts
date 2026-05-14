/**
 * Opening panels in additional windows.
 *
 * Wraps the Tauri ``open_panel_window`` command with a graceful
 * fallback for non-Tauri environments (vite dev server, hosted
 * web build).  In Tauri:
 *
 *   - macOS: the new window is given a ``tabbingIdentifier`` that
 *     matches the originating window's project, so the OS
 *     automatically merges it as a tab in the existing window.
 *     Users can then tear the tab out via the standard macOS
 *     drag-out gesture or "Move Tab to New Window" menu item.
 *   - Windows/Linux: a discrete OS window is created.  Native
 *     tab-merging gestures aren't available on those platforms;
 *     a cross-platform in-app tab bar with cross-window drag is
 *     planned for a later iteration.  See
 *     https://github.com/microsoft/clarity-agent/issues/34 for
 *     the platform-strategy notes and the per-iteration plan.
 *
 * In dev / browser mode (no Tauri IPC bridge), falls back to
 * ``window.open`` so the developer still gets a working "open
 * in new tab/window" experience while iterating in vite dev.
 */

import { buildPanelUrl, type PanelId } from "./panels";

/**
 * Open the given panel in an additional window.
 *
 * ``launcherProjectId`` is the short URL-safe project id from
 * the current window's ``useParams`` — passed in by the caller
 * since this module doesn't run in a React context.  When
 * ``null``/``undefined``, the new window uses the
 * single-project URL shape (the server's bound project is
 * implicit).
 *
 * Returns nothing on success.  Failures fall back to
 * ``window.open`` rather than throwing — opening a window in a
 * weird environment is best-effort.
 */
export async function openPanelInNewWindow(
  panelId: PanelId,
  launcherProjectId?: string | null,
): Promise<void> {
  const url = buildPanelUrl(panelId, launcherProjectId);
  let invokeError: unknown = null;
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("open_panel_window", {
      // The route portion of the URL — the Rust side combines
      // this with the current server origin to build the full
      // ``http://127.0.0.1:PORT/...`` target.  Passing only the
      // route keeps the frontend from having to know the port.
      route: url,
      // Tabbing identifier on macOS — windows that share this
      // string get auto-merged into a single tabbed window by
      // the OS.  Using the project id means all of one project's
      // panels tab together; opening a panel from a different
      // project (when multi-project lands) gets its own tab
      // group.
      tabbingId: panelId.projectId,
    });
    return;
  } catch (err) {
    invokeError = err;
  }
  // Log loudly before the fallback runs.  In a Tauri build the
  // ``window.open`` path is effectively a no-op (no browser tab
  // to open into) — so a silent invoke failure presents to the
  // user as "the button does nothing."  Surfacing the underlying
  // error in the console gives an actionable trail when the
  // command path fails (missing capability, builder error,
  // command not registered, args mismatch, etc.).
  console.warn(
    "[openPanelInNewWindow] Tauri invoke('open_panel_window') failed; " +
      "falling back to window.open(). In a Tauri build this fallback " +
      "is a no-op — the underlying error is:",
    invokeError,
  );
  window.open(url, "_blank");
}
