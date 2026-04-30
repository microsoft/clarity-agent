import { useCallback, useEffect, useRef, useState } from "react";
import type { WsClientMessage, WsServerMessage } from "../types";

interface UseWebSocketReturn {
  send: (msg: WsClientMessage) => void;
  connected: boolean;
}

/**
 * WebSocket hook that delivers every message via a stable callback.
 *
 * Previous implementation stored `lastMessage` in React state, but
 * rapid WebSocket events (e.g. tool_use during streaming) could
 * overwrite each other between renders, silently dropping messages.
 * The callback approach dispatches synchronously from the event handler
 * so no messages are lost.
 */
export function useWebSocket(
  url: string,
  onMessage: (msg: WsServerMessage) => void,
): UseWebSocketReturn {
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const reconnectDelay = useRef(1000);
  const unmountedRef = useRef(false);

  const connect = useCallback(() => {
    if (unmountedRef.current) return;

    // Build absolute WS URL
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}${url}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmountedRef.current) return;  // lame-duck mode
      setConnected(true);
      reconnectDelay.current = 1000; // reset backoff
    };

    ws.onmessage = (event: MessageEvent) => {
      if (unmountedRef.current) return;  // lame-duck mode
      try {
        const data = JSON.parse(event.data as string) as WsServerMessage;
        onMessageRef.current(data);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (!unmountedRef.current) setConnected(false);
      wsRef.current = null;
      if (unmountedRef.current) return;
      // Reconnect with exponential backoff (max 30s)
      reconnectTimer.current = setTimeout(() => {
        reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000);
        connect();
      }, reconnectDelay.current);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [url]);

  useEffect(() => {
    unmountedRef.current = false;
    connect();
    return () => {
      unmountedRef.current = true;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((msg: WsClientMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { send, connected };
}
