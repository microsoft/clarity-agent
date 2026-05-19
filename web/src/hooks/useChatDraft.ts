/**
 * Per-session chat-input draft persistence.
 *
 * Thin typed wrapper around :func:`usePanelSlot` for the specific
 * case of a chat panel's draft text.  Kept as its own hook (rather
 * than asking callers to invoke ``usePanelSlot(panelId, "draft", "")``
 * directly) so:
 *
 *   - The slot name ``"draft"`` stays an implementation detail.
 *     Callers don't need to know it, can't typo it, and we can
 *     rename it later without touching the call sites.
 *   - The caller-facing contract is type-safe: the value is
 *     specifically a string, the default is "", and the panel
 *     type is constrained to ``"chat"`` (other panel kinds have
 *     no chat-draft concept).
 *
 * See ``data/panels.ts`` for the store mechanics, PanelId
 * schema, and the rationale for using a discriminated union +
 * sessionStorage backing.  This file is intentionally short.
 */

import { useState } from "react";
import { type PanelId, usePanelSlot } from "../data/panels";

/**
 * Identifier for a chat-draft slot.  A chat-type :type:`PanelId`,
 * which encodes both project and session.  Use the broader
 * :type:`PanelId` directly when you want to pass through generic
 * panel-state hooks; this narrower alias is here so the
 * :class:`MessageInput` prop type can say "chat panel" rather
 * than "any panel."
 */
export type DraftPanelId = Extract<PanelId, { type: "chat" }>;

/**
 * Hook: chat-input draft for ``panelId``.  Behaves like
 * ``useState<string>`` for the caller — ``[value, setValue]``.
 *
 * When ``panelId`` is non-null, the value is backed by the
 * per-panel sessionStorage slot and survives mount/unmount and
 * reload.  When ``panelId`` is ``null``, the value is kept in
 * local component state instead — typing still works, it just
 * doesn't persist.
 *
 * Why fall back to local state rather than returning a no-op
 * setter: some backends (notably GitHub Copilot) don't expose
 * a stable session/thread id, so ``panelId`` is permanently
 * ``null``.  A no-op setter would mean the textarea is
 * controllable in the React sense (``value`` prop set) but
 * uneditable from the user's perspective — focus works, but
 * keystrokes vanish.  Returning a real ``useState`` setter
 * keeps the input usable; the only thing lost is persistence.
 *
 * Edge case worth flagging: if a caller mounts the hook with
 * ``null``, the user types, and then ``panelId`` becomes
 * non-null on a later render, the local draft is dropped and
 * the persistent slot's value (typically "") wins.  In
 * practice the loading window is short and the textarea is
 * usually still ``disabled`` during it, so this is rarely
 * user-visible.  If it ever becomes one, the fix is to copy
 * ``local`` into the slot on the null→id transition.
 */
export function useChatDraft(
  panelId: DraftPanelId | null,
): [string, (next: string) => void] {
  // Both hooks are called on every render to keep hook order
  // stable, but only one's state is returned.  ``usePanelSlot``
  // already no-ops its setter and returns the default when
  // ``panelId`` is null, so the unused branch is cheap.
  const [local, setLocal] = useState<string>("");
  const [persistent, setPersistent] = usePanelSlot<string>(
    panelId,
    "draft",
    "",
  );
  if (panelId === null) return [local, setLocal];
  return [persistent, setPersistent];
}
