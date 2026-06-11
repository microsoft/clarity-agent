import { describe, it, expect } from "vitest";
import { chatReducer, initialState } from "../hooks/useChat";
import type { ChatState } from "../hooks/useChat";

describe("chatReducer", () => {
  describe("send_message", () => {
    it("adds a user message and enters streaming state", () => {
      const next = chatReducer(initialState, {
        type: "send_message",
        content: "Hello",
      });
      expect(next.messages).toHaveLength(1);
      expect(next.messages[0].role).toBe("user");
      expect(next.messages[0].content).toBe("Hello");
      expect(next.messages[0].id).toBeTruthy();
      expect(next.messages[0].timestamp).toBeGreaterThan(0);
      expect(next.streaming).toBe(true);
    });

    it("clears pending tools and cost from previous turn", () => {
      const withPending: ChatState = {
        ...initialState,
        pendingTools: [{ tool: "read_file", detail: "foo.txt" }],
        turnCost: 0.05,
      };
      const next = chatReducer(withPending, {
        type: "send_message",
        content: "Next question",
      });
      expect(next.pendingTools).toEqual([]);
      expect(next.turnCost).toBe(0);
    });

    it("preserves existing messages", () => {
      const withMessage: ChatState = {
        ...initialState,
        messages: [
          { id: "1", role: "assistant", content: "Hi", timestamp: 1 },
        ],
      };
      const next = chatReducer(withMessage, {
        type: "send_message",
        content: "Follow up",
      });
      expect(next.messages).toHaveLength(2);
      expect(next.messages[0].content).toBe("Hi");
      expect(next.messages[1].content).toBe("Follow up");
    });
  });

  describe("tool_event", () => {
    it("commits each tool event as its own message in time order", () => {
      let state = chatReducer(initialState, {
        type: "send_message",
        content: "Do something",
      });
      state = chatReducer(state, {
        type: "tool_event",
        tool: "read_file",
        detail: "a.txt",
      });
      state = chatReducer(state, {
        type: "tool_event",
        tool: "write_file",
        detail: "b.txt",
      });
      // Tool events become standalone tool-role messages in the
      // history (preserves chronological order with interleaved text).
      const toolMsgs = state.messages.filter((m) => m.role === "tool");
      expect(toolMsgs).toHaveLength(2);
      expect(toolMsgs[0].toolEvents?.[0]).toEqual({
        tool: "read_file",
        detail: "a.txt",
      });
      expect(toolMsgs[1].toolEvents?.[0]).toEqual({
        tool: "write_file",
        detail: "b.txt",
      });
    });

    it("commits streaming text before a tool event", () => {
      let state = chatReducer(initialState, {
        type: "send_message",
        content: "Help me",
      });
      state = chatReducer(state, { type: "text_delta", content: "Let me " });
      state = chatReducer(state, { type: "text_delta", content: "check." });
      state = chatReducer(state, {
        type: "tool_event",
        tool: "read_file",
        detail: "a.txt",
      });
      // Streaming text should be flushed as a message before the tool.
      expect(state.streamingText).toBe("");
      // After the user message, there should be: assistant text, tool.
      const afterUser = state.messages.slice(1);
      expect(afterUser).toHaveLength(2);
      expect(afterUser[0].role).toBe("assistant");
      expect(afterUser[0].content).toBe("Let me check.");
      expect(afterUser[1].role).toBe("tool");
    });
  });

  describe("cost_event", () => {
    it("sets the turn cost", () => {
      const next = chatReducer(initialState, {
        type: "cost_event",
        cost_usd: 0.0123,
      });
      expect(next.turnCost).toBe(0.0123);
    });

    it("replaces previous cost (server sends cumulative)", () => {
      let state = chatReducer(initialState, {
        type: "cost_event",
        cost_usd: 0.01,
      });
      state = chatReducer(state, { type: "cost_event", cost_usd: 0.03 });
      expect(state.turnCost).toBe(0.03);
    });
  });

  describe("receive_response", () => {
    it("adds assistant message and exits streaming", () => {
      let state = chatReducer(initialState, {
        type: "send_message",
        content: "Q",
      });
      state = chatReducer(state, {
        type: "receive_response",
        content: "Answer",
      });
      expect(state.messages).toHaveLength(2);
      expect(state.messages[1].role).toBe("assistant");
      expect(state.messages[1].content).toBe("Answer");
      expect(state.streaming).toBe(false);
    });

    it("keeps tool events as their own messages in time order", () => {
      let state = chatReducer(initialState, {
        type: "send_message",
        content: "Q",
      });
      state = chatReducer(state, {
        type: "tool_event",
        tool: "search",
        detail: "query",
      });
      state = chatReducer(state, {
        type: "receive_response",
        content: "Found it",
      });
      // user + tool + assistant = 3 messages.
      expect(state.messages).toHaveLength(3);
      expect(state.messages[1].role).toBe("tool");
      expect(state.messages[1].toolEvents).toEqual([
        { tool: "search", detail: "query" },
      ]);
      expect(state.messages[2].role).toBe("assistant");
      expect(state.messages[2].content).toBe("Found it");
      // The final assistant message does not carry the tool events.
      expect(state.messages[2].toolEvents).toBeUndefined();
      expect(state.pendingTools).toEqual([]);
    });

    it("attaches cost to the response message", () => {
      let state = chatReducer(initialState, {
        type: "send_message",
        content: "Q",
      });
      state = chatReducer(state, { type: "cost_event", cost_usd: 0.042 });
      state = chatReducer(state, {
        type: "receive_response",
        content: "A",
      });
      expect(state.messages[1].costUsd).toBe(0.042);
    });

    it("omits toolEvents and costUsd when there are none", () => {
      let state = chatReducer(initialState, {
        type: "send_message",
        content: "Q",
      });
      state = chatReducer(state, {
        type: "receive_response",
        content: "A",
      });
      expect(state.messages[1].toolEvents).toBeUndefined();
      expect(state.messages[1].costUsd).toBeUndefined();
    });
  });

  describe("start_process", () => {
    it("sets current process and enters streaming", () => {
      const next = chatReducer(initialState, {
        type: "start_process",
        name: "problem-clarification",
      });
      expect(next.currentProcess).toBe("problem-clarification");
      expect(next.streaming).toBe(true);
      expect(next.pendingTools).toEqual([]);
      expect(next.turnCost).toBe(0);
    });
  });

  describe("model_changed", () => {
    it("updates model state", () => {
      const next = chatReducer(initialState, {
        type: "model_changed",
        tier: "deep",
        model: "claude-opus-4-20250514",
        auto: false,
      });
      expect(next.activeTier).toBe("deep");
      expect(next.activeModel).toBe("claude-opus-4-20250514");
      expect(next.autoModel).toBe(false);
    });
  });

  describe("clear", () => {
    it("resets messages and streaming but preserves model state", () => {
      const populated: ChatState = {
        messages: [
          { id: "1", role: "user", content: "Hi", timestamp: 1 },
          { id: "2", role: "assistant", content: "Hello", timestamp: 2 },
        ],
        pendingTools: [{ tool: "t", detail: "d" }],
        turnCost: 0.05,
        turnTokens: 500,
        sessionTokens: 1500,
        sessionCost: 0.10,
        streamingText: "partial response",
        outgoingQueue: ["queued message"],
        streaming: true,
        currentProcess: "problem-clarification",
        activeModel: "claude-sonnet",
        activeTier: "default",
        autoModel: false,
        error: null,
        statusPhase: null,
        historyLoaded: true,
        explorationComplete: false,
      };
      const next = chatReducer(populated, { type: "clear" });
      expect(next.messages).toEqual([]);
      expect(next.pendingTools).toEqual([]);
      expect(next.outgoingQueue).toEqual([]);
      expect(next.turnCost).toBe(0);
      expect(next.streaming).toBe(false);
      expect(next.currentProcess).toBeNull();
      // Model state preserved
      expect(next.activeModel).toBe("claude-sonnet");
      expect(next.activeTier).toBe("default");
      expect(next.autoModel).toBe(false);
    });
  });

  describe("status_event", () => {
    it("stores the phase from a status event", () => {
      const next = chatReducer(initialState, {
        type: "status_event",
        phase: "reasoning",
      });
      expect(next.statusPhase).toBe("reasoning");
    });

    it("overwrites previous phase on transition", () => {
      let state = chatReducer(initialState, {
        type: "status_event",
        phase: "thinking",
      });
      state = chatReducer(state, {
        type: "status_event",
        phase: "tool:read_file",
      });
      expect(state.statusPhase).toBe("tool:read_file");
    });

    it("is cleared by receive_response", () => {
      let state = chatReducer(initialState, {
        type: "send_message",
        content: "Q",
      });
      state = chatReducer(state, {
        type: "status_event",
        phase: "reasoning",
      });
      expect(state.statusPhase).toBe("reasoning");
      state = chatReducer(state, {
        type: "receive_response",
        content: "A",
      });
      expect(state.statusPhase).toBeNull();
    });

    it("is cleared by error_event", () => {
      let state = chatReducer(initialState, {
        type: "status_event",
        phase: "tool:write_file",
      });
      expect(state.statusPhase).toBe("tool:write_file");
      state = chatReducer(state, {
        type: "error_event",
        error: { message: "Something broke" },
      });
      expect(state.statusPhase).toBeNull();
    });

    it("is cleared by clear", () => {
      let state = chatReducer(initialState, {
        type: "status_event",
        phase: "sub-agent working",
      });
      expect(state.statusPhase).toBe("sub-agent working");
      state = chatReducer(state, { type: "clear" });
      expect(state.statusPhase).toBeNull();
    });
  });

  describe("outgoing message queue", () => {
    it("enqueue_message appends to the queue", () => {
      let state = chatReducer(initialState, {
        type: "enqueue_message",
        content: "first",
      });
      state = chatReducer(state, {
        type: "enqueue_message",
        content: "second",
      });
      expect(state.outgoingQueue).toEqual(["first", "second"]);
    });

    it("dequeue_message removes from the front", () => {
      let state = chatReducer(initialState, {
        type: "enqueue_message",
        content: "first",
      });
      state = chatReducer(state, {
        type: "enqueue_message",
        content: "second",
      });
      state = chatReducer(state, { type: "dequeue_message" });
      expect(state.outgoingQueue).toEqual(["second"]);
    });
  });

  describe("full conversation flow", () => {
    it("handles a complete send → tools → cost → response cycle", () => {
      let s = initialState;

      // User sends
      s = chatReducer(s, { type: "send_message", content: "Analyze this" });
      expect(s.messages).toHaveLength(1);
      expect(s.streaming).toBe(true);

      // Server streams tool events — each becomes a tool-role message.
      s = chatReducer(s, {
        type: "tool_event",
        tool: "read_file",
        detail: "main.py",
      });
      s = chatReducer(s, {
        type: "tool_event",
        tool: "read_file",
        detail: "tests.py",
      });
      // After 2 tool events: user msg + 2 tool msgs = 3.
      expect(s.messages).toHaveLength(3);
      expect(s.messages[1].role).toBe("tool");
      expect(s.messages[2].role).toBe("tool");

      // Server sends cost
      s = chatReducer(s, { type: "cost_event", cost_usd: 0.015 });

      // Server sends response — appends the assistant message with text + cost.
      s = chatReducer(s, {
        type: "receive_response",
        content: "Here's my analysis",
      });
      // Now: user + 2 tool + assistant = 4.
      expect(s.messages).toHaveLength(4);
      expect(s.streaming).toBe(false);
      const finalMsg = s.messages[3];
      expect(finalMsg.role).toBe("assistant");
      expect(finalMsg.content).toBe("Here's my analysis");
      expect(finalMsg.costUsd).toBe(0.015);
      expect(s.pendingTools).toEqual([]);
    });
  });

  describe("load_history", () => {
    it("replaces messages with the payload and flips historyLoaded", () => {
      // Initial state has empty messages and historyLoaded=false.
      // The fetch resolves; dispatch fills the list and flips the
      // flag, unblocking the auto-start gate in ChatPanel.
      const history = [
        { id: "h1", role: "user" as const, content: "earlier", timestamp: 100 },
        { id: "h2", role: "assistant" as const, content: "reply", timestamp: 200 },
      ];
      const next = chatReducer(initialState, {
        type: "load_history",
        messages: history,
      });
      expect(next.messages).toEqual(history);
      expect(next.historyLoaded).toBe(true);
    });

    it("flips historyLoaded even when payload is empty", () => {
      // Empty history is a meaningful "fresh project" signal — the
      // auto-start needs to fire in that case, which requires
      // historyLoaded=true.
      const next = chatReducer(initialState, {
        type: "load_history",
        messages: [],
      });
      expect(next.messages).toEqual([]);
      expect(next.historyLoaded).toBe(true);
    });

    it("doesn't disturb non-message state fields", () => {
      // The reducer should narrow its blast radius — model state,
      // session totals, errors etc. should pass through unchanged.
      const seeded = {
        ...initialState,
        activeModel: "claude-sonnet",
        activeTier: "default",
        sessionTokens: 12345,
      };
      const next = chatReducer(seeded, {
        type: "load_history",
        messages: [{ id: "h", role: "user", content: "x", timestamp: 1 }],
      });
      expect(next.activeModel).toBe("claude-sonnet");
      expect(next.activeTier).toBe("default");
      expect(next.sessionTokens).toBe(12345);
    });
  });

  describe("clear preserves historyLoaded", () => {
    it("clear after history-load keeps historyLoaded=true", () => {
      // After "Start new chapter" we dispatch ``clear``.  The new
      // chapter is empty so re-fetching history would return an
      // empty list anyway — but we shouldn't reset the flag,
      // otherwise the auto-start would race the second fetch.
      const populated = chatReducer(initialState, {
        type: "load_history",
        messages: [{ id: "h", role: "user", content: "x", timestamp: 1 }],
      });
      const cleared = chatReducer(populated, { type: "clear" });
      expect(cleared.messages).toEqual([]);
      expect(cleared.historyLoaded).toBe(true);
    });
  });
});
