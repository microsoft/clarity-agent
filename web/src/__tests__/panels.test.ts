/**
 * Tests for ``data/panels.ts`` — :type:`PanelId` serialization and
 * the generic per-panel slot store (``getSlot`` / ``setSlot`` /
 * ``usePanelSlot``).
 *
 * Specific typed wrappers like ``useChatDraft`` are tested
 * separately in :file:`useChatDraft.test.ts` — those test the
 * thin wrapper's API; the substrate behaviors (persistence
 * across mount, isolation by key, sessionStorage hydration,
 * etc.) are exercised here against the generic ``usePanelSlot``.
 */

import { renderHook, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  type PanelId,
  __resetPanelsForTest,
  buildPanelUrl,
  getSlot,
  panelRoute,
  serializePanelId,
  setSlot,
  usePanelSlot,
} from "../data/panels";

const chatA: PanelId = {
  projectId: "/Users/test/proj-a",
  type: "chat",
  threadId: "session-1",
};
const chatA2: PanelId = {
  projectId: "/Users/test/proj-a",
  type: "chat",
  threadId: "session-2",
};
const chatB: PanelId = {
  projectId: "/Users/test/proj-b",
  type: "chat",
  threadId: "session-1",
};
const historyA: PanelId = {
  projectId: "/Users/test/proj-a",
  type: "history",
};
const protocolA: PanelId = {
  projectId: "/Users/test/proj-a",
  type: "protocol",
};
const protocolDocA: PanelId = {
  projectId: "/Users/test/proj-a",
  type: "protocol",
  docPath: "decisions/why.md",
};

beforeEach(() => {
  sessionStorage.clear();
  __resetPanelsForTest();
});

afterEach(() => {
  sessionStorage.clear();
  __resetPanelsForTest();
});

// ---------------------------------------------------------------------------
// serializePanelId — must be stable, readable, and disambiguate all panel
// shapes that are semantically distinct.
// ---------------------------------------------------------------------------

describe("serializePanelId", () => {
  it("encodes project, type, and thread for chat panels", () => {
    const s = serializePanelId(chatA);
    expect(s).toContain(chatA.projectId);
    expect(s).toContain("chat");
    expect(s).toContain(chatA.threadId);
  });

  it("distinguishes chat panels by thread id", () => {
    expect(serializePanelId(chatA)).not.toBe(serializePanelId(chatA2));
  });

  it("distinguishes chat panels by project id", () => {
    expect(serializePanelId(chatA)).not.toBe(serializePanelId(chatB));
  });

  it("encodes type for non-chat panels with no disambiguator", () => {
    const s = serializePanelId(historyA);
    expect(s).toContain("history");
    expect(s).toContain(historyA.projectId);
  });

  it("disambiguates protocol panels by docPath when present", () => {
    expect(serializePanelId(protocolA)).not.toBe(
      serializePanelId(protocolDocA),
    );
    expect(serializePanelId(protocolDocA)).toContain("decisions/why.md");
  });

  it("treats protocol-with-no-docPath and protocol-with-docPath as different", () => {
    // Regression guard: a careless implementation could
    // accidentally serialize them identically (e.g., by stripping
    // an empty docPath).  Different panels must have different
    // serializations, period.
    const root = serializePanelId(protocolA);
    const withDoc = serializePanelId(protocolDocA);
    expect(root).not.toBe(withDoc);
  });

  it("produces stable output across calls", () => {
    expect(serializePanelId(chatA)).toBe(serializePanelId(chatA));
  });
});

// ---------------------------------------------------------------------------
// panelRoute / buildPanelUrl — PanelId → URL mappings used by
// "Open in new window" and similar navigation actions.
// ---------------------------------------------------------------------------

describe("panelRoute", () => {
  it("maps each panel type to its react-router route", () => {
    expect(panelRoute(chatA)).toBe("/");
    expect(panelRoute(historyA)).toBe("/history");
    expect(panelRoute(protocolA)).toBe("/protocol");
    expect(
      panelRoute({ projectId: "/x", type: "packet" }),
    ).toBe("/packet");
    expect(
      panelRoute({ projectId: "/x", type: "packet-status" }),
    ).toBe("/packet-status");
  });

  it("returns the same route regardless of disambiguator", () => {
    // v1 contract: the route only encodes the panel TYPE, not
    // per-instance state.  When a window opens at this route,
    // the server's session state determines which session/doc
    // is shown.  Per-instance routing (e.g., /protocol/<docPath>)
    // is a future step.
    expect(panelRoute(chatA)).toBe(panelRoute(chatA2));
    expect(panelRoute(protocolA)).toBe(panelRoute(protocolDocA));
  });
});

describe("buildPanelUrl", () => {
  it("returns the bare route in single-project mode", () => {
    expect(buildPanelUrl(historyA)).toBe("/history");
    expect(buildPanelUrl(historyA, null)).toBe("/history");
    expect(buildPanelUrl(historyA, undefined)).toBe("/history");
  });

  it("prefixes /p/<launcherProjectId> in launcher mode", () => {
    expect(buildPanelUrl(historyA, "abc123")).toBe("/p/abc123/history");
    expect(buildPanelUrl(protocolA, "abc123")).toBe("/p/abc123/protocol");
  });

  it("uses /p/<id>/ (not /p/<id>) for the chat root route", () => {
    // Guard against accidentally emitting "/p/abc123" with no
    // trailing slash, which routes differently from "/p/abc123/"
    // under react-router and produces "Not Found" for the chat
    // route specifically.
    expect(buildPanelUrl(chatA, "abc123")).toBe("/p/abc123/");
  });

  it("uses the launcher short id, NOT PanelId.projectId, for the URL", () => {
    // PanelId.projectId is the canonical absolute path (used as a
    // state-storage key); the URL's launcher prefix uses the
    // short id from the project registry.  This regression guard
    // catches a future change that accidentally puts the
    // path-based projectId into the URL.
    const longPath = "/Users/yzunger/src/some-deep/project-path";
    const panel: PanelId = {
      projectId: longPath,
      type: "history",
    };
    const url = buildPanelUrl(panel, "abc123");
    expect(url).toBe("/p/abc123/history");
    expect(url).not.toContain(longPath);
  });
});


// ---------------------------------------------------------------------------
// Generic slot store — non-React access
// ---------------------------------------------------------------------------

describe("getSlot / setSlot", () => {
  it("returns the default value when no value has been stored", () => {
    expect(getSlot(chatA, "draft", "default")).toBe("default");
  });

  it("returns the stored value after a write", () => {
    setSlot(chatA, "draft", "hello");
    expect(getSlot(chatA, "draft", "default")).toBe("hello");
  });

  it("stores arbitrary JSON-serializable types, not just strings", () => {
    // The store backs sessionStorage with JSON encoding so
    // non-string slot values (numbers, objects, booleans) work
    // uniformly.  Verify the round-trip preserves them.
    setSlot<number>(historyA, "scroll", 1234);
    expect(getSlot<number>(historyA, "scroll", 0)).toBe(1234);

    setSlot(historyA, "filters", { tag: "auth", since: "yesterday" });
    expect(
      getSlot(historyA, "filters", {} as Record<string, string>),
    ).toEqual({ tag: "auth", since: "yesterday" });
  });

  it("isolates different slots on the same panel", () => {
    setSlot(chatA, "draft", "draft text");
    setSlot(chatA, "scroll", 42);
    expect(getSlot(chatA, "draft", "")).toBe("draft text");
    expect(getSlot(chatA, "scroll", 0)).toBe(42);
  });

  it("isolates the same slot name across different panels", () => {
    setSlot(chatA, "scroll", 100);
    setSlot(historyA, "scroll", 999);
    expect(getSlot(chatA, "scroll", 0)).toBe(100);
    expect(getSlot(historyA, "scroll", 0)).toBe(999);
  });
});

// ---------------------------------------------------------------------------
// usePanelSlot — React hook
// ---------------------------------------------------------------------------

describe("usePanelSlot — basic reactivity", () => {
  it("returns the default value initially and updates on setValue", () => {
    const { result } = renderHook(() =>
      usePanelSlot(chatA, "draft", ""),
    );
    expect(result.current[0]).toBe("");
    act(() => result.current[1]("typed"));
    expect(result.current[0]).toBe("typed");
  });
});

describe("usePanelSlot — persistence across mount/unmount", () => {
  it("preserves the value across remount with the same panelId+slot", () => {
    const first = renderHook(() => usePanelSlot(chatA, "draft", ""));
    act(() => first.result.current[1]("half-typed"));
    first.unmount();

    const second = renderHook(() => usePanelSlot(chatA, "draft", ""));
    expect(second.result.current[0]).toBe("half-typed");
  });

  it("preserves the value when panelId changes and changes back", () => {
    const { result, rerender } = renderHook(
      ({ id }: { id: PanelId }) => usePanelSlot(id, "draft", ""),
      { initialProps: { id: chatA } },
    );
    act(() => result.current[1]("for chat A"));

    rerender({ id: chatB });
    expect(result.current[0]).toBe("");
    act(() => result.current[1]("for chat B"));

    rerender({ id: chatA });
    expect(result.current[0]).toBe("for chat A");
  });
});

describe("usePanelSlot — key isolation", () => {
  it("different sessions under the same project do not collide", () => {
    const a = renderHook(() => usePanelSlot(chatA, "draft", ""));
    const a2 = renderHook(() => usePanelSlot(chatA2, "draft", ""));
    act(() => a.result.current[1]("session 1 draft"));
    act(() => a2.result.current[1]("session 2 draft"));
    expect(a.result.current[0]).toBe("session 1 draft");
    expect(a2.result.current[0]).toBe("session 2 draft");
  });

  it("different projects with the same session id do not collide", () => {
    // Real failure mode this guards: two projects open that
    // happen to share a session id (e.g., both "default").
    // Drafts would silently merge if the project component were
    // missing from the key.
    const a = renderHook(() => usePanelSlot(chatA, "draft", ""));
    const b = renderHook(() => usePanelSlot(chatB, "draft", ""));
    act(() => a.result.current[1]("draft in project A"));
    act(() => b.result.current[1]("draft in project B"));
    expect(a.result.current[0]).toBe("draft in project A");
    expect(b.result.current[0]).toBe("draft in project B");
  });

  it("different panel types under the same project do not collide", () => {
    const chat = renderHook(() => usePanelSlot(chatA, "draft", ""));
    const protocol = renderHook(() => usePanelSlot(protocolA, "draft", ""));
    act(() => chat.result.current[1]("chat draft"));
    act(() => protocol.result.current[1]("protocol draft"));
    expect(chat.result.current[0]).toBe("chat draft");
    expect(protocol.result.current[0]).toBe("protocol draft");
  });

  it("updating one slot does not re-render subscribers on another slot", () => {
    let draftRenders = 0;
    const draft = renderHook(() => {
      draftRenders += 1;
      return usePanelSlot(chatA, "draft", "");
    });
    const initial = draftRenders;

    // Mutate a sibling slot on the same panel.  ``draft``'s
    // subscriber list shouldn't fire — subscribers are scoped
    // (panelId, slot) not just panelId.
    const scroll = renderHook(() => usePanelSlot(chatA, "scroll", 0));
    act(() => scroll.result.current[1](999));

    expect(draftRenders).toBe(initial);
    expect(draft.result.current[0]).toBe("");
  });
});

describe("usePanelSlot — null panelId", () => {
  it("returns the default value and does not persist", () => {
    const { result, unmount } = renderHook(() =>
      usePanelSlot(null, "draft", "fallback"),
    );
    expect(result.current[0]).toBe("fallback");
    act(() => result.current[1]("typed during load"));
    expect(result.current[0]).toBe("fallback");
    unmount();

    const keys: string[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i);
      if (k) keys.push(k);
    }
    expect(keys).toEqual([]);
  });

  it("starts persisting once panelId transitions from null to a real value", () => {
    const { result, rerender } = renderHook(
      ({ id }: { id: PanelId | null }) =>
        usePanelSlot(id, "draft", ""),
      { initialProps: { id: null as PanelId | null } },
    );
    expect(result.current[0]).toBe("");

    rerender({ id: chatA });
    act(() => result.current[1]("now persisting"));
    expect(result.current[0]).toBe("now persisting");

    const second = renderHook(() => usePanelSlot(chatA, "draft", ""));
    expect(second.result.current[0]).toBe("now persisting");
  });
});

describe("usePanelSlot — sessionStorage backing", () => {
  it("writes the value to sessionStorage under a panel: namespace", () => {
    const { result } = renderHook(() => usePanelSlot(chatA, "draft", ""));
    act(() => result.current[1]("persisted text"));

    let found: string | null = null;
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i);
      if (k && k.startsWith("panel:")) {
        // The key must contain the projectId, type, threadId,
        // and slot name so a human reading sessionStorage can
        // tell what each entry is.
        expect(k).toContain(chatA.projectId);
        expect(k).toContain("chat");
        expect(k).toContain(chatA.threadId);
        expect(k).toContain("draft");
        found = sessionStorage.getItem(k);
        break;
      }
    }
    // Values are JSON-encoded uniformly, including strings.
    expect(found).toBe(JSON.stringify("persisted text"));
  });

  it("round-trips non-string values through sessionStorage", () => {
    const { result } = renderHook(() => usePanelSlot(historyA, "scroll", 0));
    act(() => result.current[1](42));

    // Remount with a fresh hook against the same panelId+slot —
    // the value should come back as a number, not a string.
    const second = renderHook(() => usePanelSlot(historyA, "scroll", 0));
    expect(second.result.current[0]).toBe(42);
    expect(typeof second.result.current[0]).toBe("number");
  });
});

describe("usePanelSlot — redundant writes", () => {
  it("setting the same value twice does not trigger an extra render", () => {
    let renders = 0;
    const { result } = renderHook(() => {
      renders += 1;
      return usePanelSlot(chatA, "draft", "");
    });
    const initial = renders;
    act(() => result.current[1]("same"));
    const afterFirst = renders;
    expect(afterFirst).toBeGreaterThan(initial);
    act(() => result.current[1]("same"));
    expect(renders).toBe(afterFirst);
  });
});
