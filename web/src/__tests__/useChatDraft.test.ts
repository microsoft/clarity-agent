/**
 * Tests for ``useChatDraft`` — the thin typed wrapper over the
 * generic panel-slot store.
 *
 * The substrate behaviors (persistence across mount/unmount, key
 * isolation, sessionStorage hydration, null-panelId fallback,
 * subscriber scoping) are tested in :file:`panels.test.ts`
 * against ``usePanelSlot``.  This file only verifies the
 * wrapper-specific contract: the right slot name is used, the
 * default value is the empty string, and the value type is
 * ``string``.
 */

import { renderHook, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  type PanelId,
  __resetPanelsForTest,
  getSlot,
} from "../data/panels";
import { type DraftPanelId, useChatDraft } from "../hooks/useChatDraft";

const chatA: DraftPanelId = {
  projectId: "/Users/test/proj-a",
  type: "chat",
  threadId: "session-1",
};

beforeEach(() => {
  sessionStorage.clear();
  __resetPanelsForTest();
});

afterEach(() => {
  sessionStorage.clear();
  __resetPanelsForTest();
});

describe("useChatDraft", () => {
  it("returns the empty string as the initial value", () => {
    const { result } = renderHook(() => useChatDraft(chatA));
    expect(result.current[0]).toBe("");
  });

  it("updates and reads back via the [value, setValue] tuple", () => {
    const { result } = renderHook(() => useChatDraft(chatA));
    act(() => result.current[1]("hello"));
    expect(result.current[0]).toBe("hello");
  });

  it("stores under the 'draft' slot on the supplied panelId", () => {
    // The wrapper uses a fixed slot name; verify by reading the
    // underlying store directly.  This is the contract that
    // future hooks (``useScrollPosition``, etc.) rely on — slot
    // names must be distinct or they collide on the same panel.
    const { result } = renderHook(() => useChatDraft(chatA));
    act(() => result.current[1]("written via wrapper"));
    expect(getSlot(chatA, "draft", "default-not-seen")).toBe(
      "written via wrapper",
    );
  });

  it("handles null panelId without persisting", () => {
    const { result, unmount } = renderHook(() => useChatDraft(null));
    expect(result.current[0]).toBe("");
    act(() => result.current[1]("ephemeral"));
    expect(result.current[0]).toBe("");
    unmount();

    // Sanity check the wrapper doesn't accidentally write under
    // a synthetic "null" key.
    const keys: string[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i);
      if (k) keys.push(k);
    }
    expect(keys).toEqual([]);
  });

  it("accepts only chat-type panel ids at the type level", () => {
    // Compile-time contract check.  This block exists so a future
    // refactor that loosens the type can't pass without someone
    // noticing.  The ``// @ts-expect-error`` directive will FAIL
    // the type-check if the expression actually type-checks
    // (i.e., if non-chat panels become assignable).
    const historyPanel: PanelId = {
      projectId: "/x",
      type: "history",
    };
    // @ts-expect-error — non-chat PanelId is not assignable to DraftPanelId
    const _wrong: DraftPanelId = historyPanel;
    void _wrong;
  });
});
