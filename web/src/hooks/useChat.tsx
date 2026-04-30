import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useReducer,
  useRef,
} from "react";
import type { ChatMessage, ProcessMeta, ToolEvent, WsClientMessage, WsServerMessage } from "../types";
import { getProcesses } from "../api/client";
import { useWebSocket } from "./useWebSocket";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

export interface ErrorInfo {
  message: string;
  category?: string;
  hint?: string;
  retryable?: boolean;
}

export interface ChatState {
  messages: ChatMessage[];
  pendingTools: ToolEvent[];
  /** Cumulative cost (USD) for the current streaming turn. */
  turnCost: number;
  /** Tokens used in the current streaming turn. */
  turnTokens: number;
  /** Total tokens used across all turns in this session. */
  sessionTokens: number;
  /** Total cost across all turns in this session. */
  sessionCost: number;
  /** Text accumulated from text_delta events during streaming. */
  streamingText: string;
  /** FIFO queue of chat messages the user typed while streaming. */
  outgoingQueue: string[];
  streaming: boolean;
  currentProcess: string | null;
  activeModel: string | null;
  activeTier: string | null;
  autoModel: boolean;
  error: ErrorInfo | null;
}

export type ChatAction =
  | { type: "send_message"; content: string }
  | { type: "enqueue_message"; content: string }
  | { type: "dequeue_message" }
  | { type: "tool_event"; tool: string; detail: string }
  | { type: "text_delta"; content: string }
  | { type: "cost_event"; cost_usd: number }
  | { type: "usage_event"; input_tokens: number; output_tokens: number }
  | { type: "receive_response"; content: string }
  | { type: "start_process"; name: string }
  | { type: "process_starting"; name: string; displayName: string; oneLiner: string }
  | { type: "model_changed"; tier: string; model: string; auto: boolean }
  | { type: "error_event"; error: ErrorInfo }
  | { type: "warning_event"; message: string }
  | { type: "dismiss_error" }
  | { type: "clear" };

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "send_message":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: crypto.randomUUID(),
            role: "user",
            content: action.content,
            timestamp: Date.now(),
          },
        ],
        pendingTools: [],
        turnCost: 0,
        turnTokens: 0,
        streamingText: "",
        streaming: true,
        error: null,
      };

    case "enqueue_message":
      return {
        ...state,
        outgoingQueue: [...state.outgoingQueue, action.content],
      };

    case "dequeue_message":
      return {
        ...state,
        outgoingQueue: state.outgoingQueue.slice(1),
      };

    case "text_delta":
      return {
        ...state,
        streamingText: state.streamingText + action.content,
      };

    case "tool_event": {
      // Commit any accumulated streaming text, then commit the tool
      // event as its own message — everything stays in time order.
      const msgs = [...state.messages];
      let newStreamingText = state.streamingText;
      if (state.streamingText) {
        msgs.push({
          id: crypto.randomUUID(),
          role: "assistant",
          content: state.streamingText,
          timestamp: Date.now(),
        });
        newStreamingText = "";
      }
      msgs.push({
        id: crypto.randomUUID(),
        role: "tool",
        content: `${action.tool}: ${action.detail}`,
        toolEvents: [{ tool: action.tool, detail: action.detail }],
        timestamp: Date.now(),
      });
      return {
        ...state,
        messages: msgs,
        streamingText: newStreamingText,
        pendingTools: [],
      };
    }

    case "cost_event":
      return {
        ...state,
        turnCost: action.cost_usd,
      };

    case "usage_event": {
      const turnDelta = action.input_tokens + action.output_tokens;
      return {
        ...state,
        turnTokens: state.turnTokens + turnDelta,
        sessionTokens: state.sessionTokens + turnDelta,
      };
    }

    case "receive_response": {
      const finalMsgs = [...state.messages];

      // Commit any remaining streaming text as a final message.
      const remainingText = state.streamingText || action.content;
      if (remainingText) {
        finalMsgs.push({
          id: crypto.randomUUID(),
          role: "assistant",
          content: remainingText,
          costUsd: state.turnCost > 0 ? state.turnCost : undefined,
          tokenCount: state.turnTokens > 0 ? state.turnTokens : undefined,
          timestamp: Date.now(),
        });
      }

      return {
        ...state,
        messages: finalMsgs,
        pendingTools: [],
        streamingText: "",
        sessionCost: state.sessionCost + state.turnCost,
        streaming: false,
      };
    }

    case "start_process":
      return {
        ...state,
        currentProcess: action.name,
        streaming: true,
        pendingTools: [],
        turnCost: 0,
        turnTokens: 0,
        streamingText: "",
        error: null,
      };

    case "process_starting":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: crypto.randomUUID(),
            role: "system",
            content: action.oneLiner,
            processName: action.name,
            timestamp: Date.now(),
          },
        ],
      };

    case "model_changed":
      return {
        ...state,
        activeModel: action.model,
        activeTier: action.tier,
        autoModel: action.auto,
      };

    case "error_event":
      return {
        ...state,
        error: action.error,
        streaming: false,
      };

    case "warning_event":
      // Non-fatal: show a dismissible banner without interrupting streaming.
      return {
        ...state,
        error: { message: action.message, category: "warning", retryable: false },
      };

    case "dismiss_error":
      return {
        ...state,
        error: null,
      };

    case "clear":
      return {
        messages: [],
        pendingTools: [],
        turnCost: 0,
        turnTokens: 0,
        sessionTokens: 0,
        sessionCost: 0,
        streamingText: "",
        outgoingQueue: [],
        streaming: false,
        currentProcess: null,
        activeModel: state.activeModel,
        activeTier: state.activeTier,
        autoModel: state.autoModel,
        error: null,
      };

    default:
      return state;
  }
}

export const initialState: ChatState = {
  messages: [],
  pendingTools: [],
  turnCost: 0,
  turnTokens: 0,
  sessionTokens: 0,
  sessionCost: 0,
  streamingText: "",
  outgoingQueue: [],
  streaming: false,
  currentProcess: null,
  activeModel: null,
  activeTier: null,
  autoModel: true,
  error: null,
};

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

export interface UseChatReturn {
  messages: ChatMessage[];
  pendingTools: ToolEvent[];
  turnCost: number;
  turnTokens: number;
  sessionTokens: number;
  sessionCost: number;
  streamingText: string;
  /** Number of messages waiting to be sent (typed while streaming). */
  queuedMessages: number;
  streaming: boolean;
  currentProcess: string | null;
  connected: boolean;
  activeModel: string | null;
  activeTier: string | null;
  autoModel: boolean;
  error: ErrorInfo | null;
  sendMessage: (text: string) => void;
  startProcess: (name: string) => void;
  stopGeneration: () => void;
  setModelOverride: (tier: string) => void;
  newSession: () => void;
  dismissError: () => void;
}

const ChatContext = createContext<UseChatReturn | null>(null);

/**
 * Provider component that owns the WebSocket connection and chat state.
 * Mount this once in the layout so it survives route changes.
 */
export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const processMetaRef = useRef<Map<string, ProcessMeta>>(new Map());

  // Fetch and cache process metadata once
  useEffect(() => {
    getProcesses()
      .then((r) => {
        const map = new Map<string, ProcessMeta>();
        for (const p of r.processes) map.set(p.name, p);
        processMetaRef.current = map;
      })
      .catch(() => {});
  }, []);

  // Dispatch directly from the WebSocket event handler so no messages
  // are lost between renders (the old useState/useEffect pattern dropped
  // rapid-fire tool_use events that arrived within the same render cycle).
  const handleWsMessage = useCallback((msg: WsServerMessage) => {
    switch (msg.type) {
      case "tool_use":
        dispatch({ type: "tool_event", tool: msg.tool, detail: msg.detail });
        break;
      case "text_delta":
        dispatch({ type: "text_delta", content: msg.content });
        break;
      case "cost":
        dispatch({ type: "cost_event", cost_usd: msg.cost_usd });
        break;
      case "usage":
        dispatch({ type: "usage_event", input_tokens: msg.input_tokens, output_tokens: msg.output_tokens });
        break;
      case "response":
        dispatch({ type: "receive_response", content: msg.content });
        break;
      case "model_changed":
        dispatch({ type: "model_changed", tier: msg.tier, model: msg.model, auto: msg.auto });
        break;
      case "session_started":
        dispatch({ type: "clear" });
        break;
      case "warning":
        dispatch({ type: "warning_event", message: msg.message });
        break;
      case "error":
        dispatch({
          type: "error_event",
          error: {
            message: msg.message,
            category: msg.category,
            hint: msg.hint,
            retryable: msg.retryable,
          },
        });
        break;
    }
  }, []);

  const { send, connected } = useWebSocket("/ws/chat", handleWsMessage);

  // Queue outgoing chat messages instead of sending them directly.
  // The drain effect below ships them one at a time once the backend
  // is idle.  This means the user can always keep typing without losing
  // messages, even mid-stream.
  const sendMessage = useCallback(
    (text: string) => {
      dispatch({ type: "enqueue_message", content: text });
    },
    [],
  );

  // Drain the outgoing queue: whenever we're connected and not
  // streaming and there's a queued message, dispatch the next one.
  useEffect(() => {
    if (!connected || state.streaming || state.outgoingQueue.length === 0) {
      return;
    }
    const next = state.outgoingQueue[0];
    dispatch({ type: "dequeue_message" });
    dispatch({ type: "send_message", content: next });
    send({ type: "chat", message: next } as WsClientMessage);
  }, [connected, state.streaming, state.outgoingQueue, send]);

  const startProcess = useCallback(
    (name: string) => {
      // Inject a process explainer system message if we have metadata
      const meta = processMetaRef.current.get(name);
      if (meta) {
        dispatch({
          type: "process_starting",
          name: meta.name,
          displayName: meta.display_name,
          oneLiner: meta.one_liner,
        });
      }
      dispatch({ type: "start_process", name });
      send({ type: "start_process", process: name } as WsClientMessage);
    },
    [send],
  );

  const setModelOverride = useCallback(
    (tier: string) => {
      send({ type: "set_model_override", tier } as WsClientMessage);
    },
    [send],
  );

  const stopGeneration = useCallback(() => {
    send({ type: "stop" } as WsClientMessage);
  }, [send]);

  const newSession = useCallback(() => {
    send({ type: "new_session" } as WsClientMessage);
  }, [send]);

  const dismissError = useCallback(() => {
    dispatch({ type: "dismiss_error" });
  }, []);

  const value: UseChatReturn = {
    messages: state.messages,
    pendingTools: state.pendingTools,
    turnCost: state.turnCost,
    turnTokens: state.turnTokens,
    sessionTokens: state.sessionTokens,
    sessionCost: state.sessionCost,
    streamingText: state.streamingText,
    queuedMessages: state.outgoingQueue.length,
    streaming: state.streaming,
    currentProcess: state.currentProcess,
    connected,
    activeModel: state.activeModel,
    activeTier: state.activeTier,
    autoModel: state.autoModel,
    error: state.error,
    sendMessage,
    startProcess,
    stopGeneration,
    setModelOverride,
    newSession,
    dismissError,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

/**
 * Consume the chat context. Must be used inside a {@link ChatProvider}.
 */
export function useChat(): UseChatReturn {
  const ctx = useContext(ChatContext);
  if (!ctx) {
    throw new Error("useChat must be used within a ChatProvider");
  }
  return ctx;
}
