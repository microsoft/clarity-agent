import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useWebSocket } from "../hooks/useWebSocket";

// ---------------------------------------------------------------------------
// Mock WebSocket
// ---------------------------------------------------------------------------

type WsHandler = ((event: { data: string }) => void) | null;

class MockWebSocket {
  static OPEN = 1;
  static instances: MockWebSocket[] = [];

  url: string;
  readyState = MockWebSocket.OPEN;
  onopen: (() => void) | null = null;
  onmessage: WsHandler = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    // Auto-connect on next tick
    setTimeout(() => this.onopen?.(), 0);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.closed = true;
    this.readyState = 3; // CLOSED
    this.onclose?.();
  }

  // Test helpers
  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  simulateMalformed() {
    this.onmessage?.({ data: "not json {{{" });
  }

  simulateError() {
    this.onerror?.();
  }
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket);
  // Provide window.location for URL building
  vi.stubGlobal("location", { protocol: "http:", host: "localhost:8420" });
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function latestWs(): MockWebSocket {
  return MockWebSocket.instances[MockWebSocket.instances.length - 1];
}

describe("useWebSocket", () => {
  it("connects to the correct URL", async () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket("/ws/chat", onMessage));

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(latestWs().url).toBe("ws://localhost:8420/ws/chat");
  });

  it("reports connected=true after open", async () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() => useWebSocket("/ws/chat", onMessage));

    expect(result.current.connected).toBe(false);

    // Trigger the onopen callback
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.connected).toBe(true);
  });

  it("dispatches parsed messages to onMessage callback", async () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket("/ws/chat", onMessage));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    const msg = { type: "response", content: "Hello" };
    act(() => {
      latestWs().simulateMessage(msg);
    });

    expect(onMessage).toHaveBeenCalledWith(msg);
  });

  it("ignores malformed JSON messages", async () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket("/ws/chat", onMessage));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    act(() => {
      latestWs().simulateMalformed();
    });

    expect(onMessage).not.toHaveBeenCalled();
  });

  it("sends JSON-stringified messages when connected", async () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() => useWebSocket("/ws/chat", onMessage));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    act(() => {
      result.current.send({ type: "chat", message: "Hello" });
    });

    expect(latestWs().sent).toEqual([
      JSON.stringify({ type: "chat", message: "Hello" }),
    ]);
  });

  it("does not send when WebSocket is not open", async () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() => useWebSocket("/ws/chat", onMessage));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    // Force closed state
    latestWs().readyState = 3;

    act(() => {
      result.current.send({ type: "chat", message: "Hello" });
    });

    expect(latestWs().sent).toEqual([]);
  });

  it("reconnects after close with backoff", async () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() => useWebSocket("/ws/chat", onMessage));

    // Let initial connection open
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.connected).toBe(true);
    expect(MockWebSocket.instances).toHaveLength(1);

    // Simulate the server closing the connection
    await act(async () => {
      latestWs().onclose?.();
    });
    expect(result.current.connected).toBe(false);

    // Before the delay, no reconnect yet
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(MockWebSocket.instances).toHaveLength(1);

    // After 1s total, reconnect fires — creates a new WebSocket
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(MockWebSocket.instances).toHaveLength(2);
    expect(latestWs().url).toBe("ws://localhost:8420/ws/chat");
  });

  it("closes WebSocket on unmount", async () => {
    const onMessage = vi.fn();
    const { unmount } = renderHook(() => useWebSocket("/ws/chat", onMessage));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    const ws = latestWs();
    unmount();
    expect(ws.closed).toBe(true);
  });
});
