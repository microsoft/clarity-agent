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
 * We mock ``@tauri-apps/api/core`` via top-level ``vi.mock``
 * (hoisted by vitest) so the mock applies to the dynamic
 * ``await import(...)`` inside ``openPanelInNewWindow`` without
 * requiring per-test module-cache resets.  Per-test behaviour is
 * configured via ``vi.mocked``.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PanelId } from "../data/panels";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

import * as TauriCore from "@tauri-apps/api/core";
import { openPanelInNewWindow } from "../data/windows";

const chatA: PanelId = {
  projectId: "/Users/test/proj-a",
  type: "chat",
  threadId: "session-1",
};
const historyA: PanelId = {
  projectId: "/Users/test/proj-a",
  type: "history",
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("openPanelInNewWindow — Tauri path", () => {
  it("invokes 'open_panel_window' with the route and project's tabbingId", async () => {
    vi.mocked(TauriCore.invoke).mockResolvedValue(undefined);

    await openPanelInNewWindow(historyA, "abc123");

    expect(TauriCore.invoke).toHaveBeenCalledTimes(1);
    expect(TauriCore.invoke).toHaveBeenCalledWith("open_panel_window", {
      route: "/p/abc123/history",
      tabbingId: historyA.projectId,
      title: "Clarity — History",
    });
  });

  it("uses the bare route in single-project mode (no launcher id)", async () => {
    vi.mocked(TauriCore.invoke).mockResolvedValue(undefined);

    await openPanelInNewWindow(historyA);

    expect(TauriCore.invoke).toHaveBeenCalledWith("open_panel_window", {
      route: "/history",
      tabbingId: historyA.projectId,
      title: "Clarity — History",
    });
  });

  it("uses the chat root route '/' (or its launcher variant) for chat panels", async () => {
    vi.mocked(TauriCore.invoke).mockResolvedValue(undefined);

    await openPanelInNewWindow(chatA, "abc123");
    expect(TauriCore.invoke).toHaveBeenLastCalledWith("open_panel_window", {
      route: "/p/abc123/",
      tabbingId: chatA.projectId,
      title: "Clarity — Chat",
    });

    await openPanelInNewWindow(chatA);
    expect(TauriCore.invoke).toHaveBeenLastCalledWith("open_panel_window", {
      route: "/",
      tabbingId: chatA.projectId,
      title: "Clarity — Chat",
    });
  });
});

describe("openPanelInNewWindow — fallback path (no Tauri)", () => {
  it("falls back to window.open when @tauri-apps/api/core is unavailable", async () => {
    // Simulate "no Tauri IPC bridge": invoke rejects as if the
    // module or command is not available.
    vi.mocked(TauriCore.invoke).mockRejectedValue(
      new Error("module not available"),
    );
    const open = vi.fn();
    vi.stubGlobal("open", open);

    await openPanelInNewWindow(historyA, "abc123");

    expect(open).toHaveBeenCalledWith("/p/abc123/history", "_blank");
  });

  it("falls back to window.open when invoke throws", async () => {
    // The IPC bridge is present but the command fails.  Same
    // user-visible outcome as no bridge at all: the new window
    // opens via the browser path.
    vi.mocked(TauriCore.invoke).mockRejectedValue(
      new Error("command not registered"),
    );
    const open = vi.fn();
    vi.stubGlobal("open", open);

    await openPanelInNewWindow(historyA);

    expect(TauriCore.invoke).toHaveBeenCalledTimes(1);
    expect(open).toHaveBeenCalledWith("/history", "_blank");
  });

  it("does not double-open: invoke success path does NOT also call window.open", async () => {
    vi.mocked(TauriCore.invoke).mockResolvedValue(undefined);
    const open = vi.fn();
    vi.stubGlobal("open", open);

    await openPanelInNewWindow(historyA, "abc123");

    expect(TauriCore.invoke).toHaveBeenCalledTimes(1);
    expect(open).not.toHaveBeenCalled();
  });
});
