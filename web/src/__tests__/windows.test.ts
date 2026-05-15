/**
 * Tests for ``data/windows.ts`` — ``openPanelInNewWindow``.
 *
 * Two code paths under test:
 *
 *   1. Tauri path: ``@tauri-apps/api/core``'s ``invoke`` exists,
 *      so the function calls ``open_panel_window`` with the
 *      right route and tabbing identifier.
 *   2. Fallback path: ``invoke`` isn't available (browser dev
 *      server, hosted web build) — the function should call
 *      ``window.open`` with the same URL.
 *
 * We mock ``@tauri-apps/api/core`` via ``vi.doMock`` (and
 * re-import the module under test in each test so the mock
 * takes effect for that import) since the function uses a
 * dynamic ``await import(...)``.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PanelId } from "../data/panels";

const chatA: PanelId = {
  projectId: "/Users/test/proj-a",
  type: "chat",
  sessionId: "session-1",
};
const historyA: PanelId = {
  projectId: "/Users/test/proj-a",
  type: "history",
};

beforeEach(() => {
  vi.resetModules();
  vi.unstubAllGlobals();
});

afterEach(() => {
  vi.doUnmock("@tauri-apps/api/core");
  vi.resetModules();
  vi.unstubAllGlobals();
});

describe("openPanelInNewWindow — Tauri path", () => {
  it("invokes 'open_panel_window' with the route and project's tabbingId", async () => {
    const invoke = vi.fn().mockResolvedValue(undefined);
    vi.doMock("@tauri-apps/api/core", () => ({ invoke }));

    const { openPanelInNewWindow } = await import("../data/windows");
    await openPanelInNewWindow(historyA, "abc123");

    expect(invoke).toHaveBeenCalledTimes(1);
    expect(invoke).toHaveBeenCalledWith("open_panel_window", {
      route: "/p/abc123/history",
      tabbingId: historyA.projectId,
      title: "Clarity — History",
    });
  });

  it("uses the bare route in single-project mode (no launcher id)", async () => {
    const invoke = vi.fn().mockResolvedValue(undefined);
    vi.doMock("@tauri-apps/api/core", () => ({ invoke }));

    const { openPanelInNewWindow } = await import("../data/windows");
    await openPanelInNewWindow(historyA);

    expect(invoke).toHaveBeenCalledWith("open_panel_window", {
      route: "/history",
      tabbingId: historyA.projectId,
      title: "Clarity — History",
    });
  });

  it("uses the chat root route '/' (or its launcher variant) for chat panels", async () => {
    const invoke = vi.fn().mockResolvedValue(undefined);
    vi.doMock("@tauri-apps/api/core", () => ({ invoke }));

    const { openPanelInNewWindow } = await import("../data/windows");
    await openPanelInNewWindow(chatA, "abc123");
    expect(invoke).toHaveBeenLastCalledWith("open_panel_window", {
      route: "/p/abc123/",
      tabbingId: chatA.projectId,
      title: "Clarity — Chat",
    });

    await openPanelInNewWindow(chatA);
    expect(invoke).toHaveBeenLastCalledWith("open_panel_window", {
      route: "/",
      tabbingId: chatA.projectId,
      title: "Clarity — Chat",
    });
  });
});

describe("openPanelInNewWindow — fallback path (no Tauri)", () => {
  it("falls back to window.open when @tauri-apps/api/core fails to import", async () => {
    // Simulate "no Tauri IPC bridge": the dynamic import rejects.
    vi.doMock("@tauri-apps/api/core", () => {
      throw new Error("module not available");
    });
    const open = vi.fn();
    vi.stubGlobal("open", open);

    const { openPanelInNewWindow } = await import("../data/windows");
    await openPanelInNewWindow(historyA, "abc123");

    expect(open).toHaveBeenCalledWith("/p/abc123/history", "_blank");
  });

  it("falls back to window.open when invoke throws", async () => {
    // The IPC bridge is present but the command fails.  Same
    // user-visible outcome as no bridge at all: the new window
    // opens via the browser path.
    const invoke = vi
      .fn()
      .mockRejectedValue(new Error("command not registered"));
    vi.doMock("@tauri-apps/api/core", () => ({ invoke }));
    const open = vi.fn();
    vi.stubGlobal("open", open);

    const { openPanelInNewWindow } = await import("../data/windows");
    await openPanelInNewWindow(historyA);

    expect(invoke).toHaveBeenCalledTimes(1);
    expect(open).toHaveBeenCalledWith("/history", "_blank");
  });

  it("does not double-open: invoke success path does NOT also call window.open", async () => {
    const invoke = vi.fn().mockResolvedValue(undefined);
    vi.doMock("@tauri-apps/api/core", () => ({ invoke }));
    const open = vi.fn();
    vi.stubGlobal("open", open);

    const { openPanelInNewWindow } = await import("../data/windows");
    await openPanelInNewWindow(historyA, "abc123");

    expect(invoke).toHaveBeenCalledTimes(1);
    expect(open).not.toHaveBeenCalled();
  });
});
