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
    it("accumulates consecutive tool events in one terminal message", () => {
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
      const toolMsgs = state.messages.filter((m) => m.role === "tool");
      expect(toolMsgs).toHaveLength(1);
      expect(toolMsgs[0].toolEvents?.[0]).toEqual({
        tool: "read_file",
        detail: "a.txt",
      });
      expect(toolMsgs[0].toolEvents?.[1]).toEqual({
        tool: "write_file",
        detail: "b.txt",
      });
      expect(toolMsgs[0].content).toBe("read_file: a.txt\nwrite_file: b.txt");
    });

    it("keeps streaming text live while appending the terminal log", () => {
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
      expect(state.streamingText).toBe("Let me check.");
      const afterUser = state.messages.slice(1);
      expect(afterUser).toHaveLength(1);
      expect(afterUser[0].role).toBe("tool");
    });
  });

  describe("log_event", () => {
    it("initializes a terminal log even when no answer is streaming", () => {
      const state = chatReducer(initialState, {
        type: "log_event",
        source: "launcher",
        level: "info",
        message: "spawned project server pid=123 port=456",
      });
      expect(state.messages).toHaveLength(1);
      expect(state.messages[0].role).toBe("tool");
      expect(state.messages[0].toolEvents).toEqual([
        {
          tool: "launcher",
          detail: "spawned project server pid=123 port=456",
        },
      ]);
    });

    it("appends idle backend logs after conversation history", () => {
      const historyState = chatReducer(initialState, {
        type: "load_history",
        messages: [
          { id: "u1", role: "user", content: "Question", timestamp: 1 },
          { id: "a1", role: "assistant", content: "Answer", timestamp: 2 },
        ],
      });

      const next = chatReducer(historyState, {
        type: "log_event",
        source: "food-match-clarity",
        level: "info",
        message: 'INFO: 127.0.0.1:61245 - "GET /api/session HTTP/1.1" 200 OK',
      });

      expect(next.messages.map((m) => m.role)).toEqual([
        "user",
        "assistant",
        "tool",
      ]);
      expect(next.messages[2].toolEvents).toEqual([
        {
          tool: "food-match-clarity",
          detail: 'INFO: 127.0.0.1:61245 - "GET /api/session HTTP/1.1" 200 OK',
        },
      ]);
    });

    it("still appends idle backend errors after conversation history", () => {
      const historyState = chatReducer(initialState, {
        type: "load_history",
        messages: [
          { id: "u1", role: "user", content: "Question", timestamp: 1 },
          { id: "a1", role: "assistant", content: "Answer", timestamp: 2 },
        ],
      });

      const next = chatReducer(historyState, {
        type: "log_event",
        source: "backend",
        level: "error",
        message: "connection failed",
      });

      expect(next.messages.map((m) => m.role)).toEqual([
        "user",
        "assistant",
        "tool",
      ]);
      expect(next.messages[2].toolEvents).toEqual([
        { tool: "backend", detail: "error: connection failed" },
      ]);
    });

    it("accumulates backend logs after a user message in the active terminal", () => {
      let state = chatReducer(initialState, {
        type: "send_message",
        content: "Question",
      });
      state = chatReducer(state, {
        type: "log_event",
        source: "food-match-clarity:err",
        level: "error",
        message: "INFO: connection open",
      });
      state = chatReducer(state, {
        type: "tool_event",
        tool: "view",
        detail: "README.md",
      });

      expect(state.messages.map((m) => m.role)).toEqual(["user", "tool"]);
      expect(state.messages[1].toolEvents).toEqual([
        {
          tool: "food-match-clarity:err",
          detail: "error: INFO: connection open",
        },
        { tool: "view", detail: "README.md" },
      ]);
    });

    it("merges runtime logs into a terminal-only assistant message", () => {
      const state = chatReducer(
        {
          ...initialState,
          messages: [
            {
              id: "terminal-assistant",
              role: "assistant",
              content: "",
              toolEvents: [{ tool: "bash", detail: "npm run build" }],
              timestamp: 1,
            },
          ],
        },
        {
          type: "log_event",
          source: "backend",
          level: "info",
          message: "chat backend ready",
        },
      );

      expect(state.messages).toHaveLength(1);
      expect(state.messages[0].toolEvents).toEqual([
        { tool: "bash", detail: "npm run build" },
        { tool: "backend", detail: "chat backend ready" },
      ]);
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

    it("adds cost to the active terminal log while streaming", () => {
      let state = chatReducer(initialState, {
        type: "send_message",
        content: "Q",
      });
      state = chatReducer(state, { type: "cost_event", cost_usd: 0.03 });
      expect(state.messages[1].role).toBe("tool");
      expect(state.messages[1].toolEvents).toEqual([
        { tool: "cost", detail: "$0.0300" },
      ]);
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

    it("keeps the terminal log between user and assistant messages", () => {
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
      expect(state.messages).toHaveLength(3);
      expect(state.messages.map((m) => m.role)).toEqual([
        "user",
        "tool",
        "assistant",
      ]);
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
      expect(state.messages.map((m) => m.role)).toEqual([
        "user",
        "tool",
        "assistant",
      ]);
      expect(state.messages[2].costUsd).toBe(0.042);
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
      expect(next.messages).toHaveLength(1);
      expect(next.messages[0].role).toBe("tool");
      expect(next.messages[0].toolEvents).toEqual([
        { tool: "process", detail: "starting problem-clarification" },
      ]);
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
      expect(next.messages).toHaveLength(0);
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

    it("adds status transitions to the active terminal log while streaming", () => {
      let state = chatReducer(initialState, {
        type: "send_message",
        content: "Q",
      });
      state = chatReducer(state, {
        type: "status_event",
        phase: "thinking",
      });
      state = chatReducer(state, {
        type: "status_event",
        phase: "tool:view (README.md)",
      });
      expect(state.messages.map((m) => m.role)).toEqual(["user", "tool"]);
      expect(state.messages[1].toolEvents).toEqual([
        { tool: "status", detail: "thinking" },
        { tool: "status", detail: "tool:view (README.md)" },
      ]);
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

      // Server streams status and tool events into one terminal log.
      s = chatReducer(s, {
        type: "status_event",
        phase: "thinking",
      });
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
      expect(s.messages).toHaveLength(2);
      expect(s.messages[1].role).toBe("tool");
      expect(s.messages[1].toolEvents).toHaveLength(3);

      // Server sends cost
      s = chatReducer(s, { type: "cost_event", cost_usd: 0.015 });
      expect(s.messages[1].toolEvents).toHaveLength(4);

      // Server sends response, then appends the assistant message with text and cost.
      s = chatReducer(s, {
        type: "receive_response",
        content: "Here's my analysis",
      });
      expect(s.messages).toHaveLength(3);
      expect(s.streaming).toBe(false);
      expect(s.messages.map((m) => m.role)).toEqual([
        "user",
        "tool",
        "assistant",
      ]);
      const finalMsg = s.messages[2];
      expect(finalMsg.role).toBe("assistant");
      expect(finalMsg.content).toBe("Here's my analysis");
      expect(finalMsg.costUsd).toBe(0.015);
      expect(s.pendingTools).toEqual([]);
    });

    it("starts a fresh terminal log for each user turn", () => {
      let s = initialState;

      s = chatReducer(s, { type: "send_message", content: "First" });
      s = chatReducer(s, { type: "status_event", phase: "thinking" });
      s = chatReducer(s, {
        type: "tool_event",
        tool: "view",
        detail: "a.md",
      });
      s = chatReducer(s, { type: "receive_response", content: "First answer" });

      s = chatReducer(s, { type: "send_message", content: "Second" });
      s = chatReducer(s, { type: "status_event", phase: "thinking" });
      s = chatReducer(s, {
        type: "tool_event",
        tool: "view",
        detail: "b.md",
      });
      s = chatReducer(s, { type: "receive_response", content: "Second answer" });

      expect(s.messages.map((m) => m.role)).toEqual([
        "user",
        "tool",
        "assistant",
        "user",
        "tool",
        "assistant",
      ]);
      expect(s.messages[1].toolEvents).toEqual([
        { tool: "status", detail: "thinking" },
        { tool: "view", detail: "a.md" },
      ]);
      expect(s.messages[4].toolEvents).toEqual([
        { tool: "status", detail: "thinking" },
        { tool: "view", detail: "b.md" },
      ]);
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
      // Empty history is a meaningful "fresh project" signal. The
      // auto-start needs to fire in that case, which requires
      // historyLoaded=true.
      const next = chatReducer(initialState, {
        type: "load_history",
        messages: [],
      });
      expect(next.messages).toEqual([]);
      expect(next.historyLoaded).toBe(true);
    });

    it("keeps launch terminal logs when empty history resolves after them", () => {
      const withLaunchLog = chatReducer(initialState, {
        type: "log_event",
        source: "launcher",
        level: "info",
        message: "spawned project server pid=123 port=456",
      });

      const next = chatReducer(withLaunchLog, {
        type: "load_history",
        messages: [],
      });

      expect(next.messages).toEqual(withLaunchLog.messages);
      expect(next.historyLoaded).toBe(true);
    });

    it("doesn't disturb non-message state fields", () => {
      // The reducer should narrow its blast radius. Model state,
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
      // empty list anyway, but we shouldn't reset the flag,
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
