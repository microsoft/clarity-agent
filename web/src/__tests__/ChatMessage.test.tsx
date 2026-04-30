import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ChatMessage from "../components/ChatMessage";
import type { ChatMessage as ChatMessageType } from "../types";

function makeMessage(overrides: Partial<ChatMessageType> = {}): ChatMessageType {
  return {
    id: "msg-1",
    role: "user",
    content: "Hello world",
    timestamp: Date.now(),
    ...overrides,
  };
}

describe("ChatMessage", () => {
  it("renders user message content", () => {
    render(<ChatMessage message={makeMessage({ content: "Test question" })} />);
    expect(screen.getByText("Test question")).toBeInTheDocument();
  });

  it("renders assistant message with markdown", () => {
    render(
      <ChatMessage
        message={makeMessage({
          role: "assistant",
          content: "Here is **bold** text",
        })}
      />,
    );
    // react-markdown renders bold as <strong>
    expect(screen.getByText("bold")).toBeInTheDocument();
    const strong = screen.getByText("bold");
    expect(strong.tagName).toBe("STRONG");
  });

  it("shows tool events for assistant messages", () => {
    render(
      <ChatMessage
        message={makeMessage({
          role: "assistant",
          content: "Done",
          toolEvents: [
            { tool: "read_file", detail: "main.py" },
            { tool: "write_file", detail: "output.txt" },
          ],
        })}
      />,
    );
    // Component renders "→ read_file: main.py" — tool name without brackets
    expect(screen.getByText(/read_file/)).toBeInTheDocument();
    expect(screen.getByText(/main\.py/)).toBeInTheDocument();
    expect(screen.getByText(/write_file/)).toBeInTheDocument();
  });

  it("shows cost for assistant messages", () => {
    render(
      <ChatMessage
        message={makeMessage({
          role: "assistant",
          content: "Result",
          costUsd: 0.0567,
        })}
      />,
    );
    // Component renders "$0.0567" without a "Cost:" prefix
    expect(screen.getByText("$0.0567")).toBeInTheDocument();
  });

  it("does not show tool events or cost for user messages", () => {
    const { container } = render(
      <ChatMessage
        message={makeMessage({
          role: "user",
          content: "Question",
          toolEvents: [{ tool: "search", detail: "query" }],
          costUsd: 0.01,
        })}
      />,
    );
    expect(container.querySelector(".font-mono")).toBeNull();
  });

  it("does not render tool/cost section when assistant has neither", () => {
    const { container } = render(
      <ChatMessage
        message={makeMessage({
          role: "assistant",
          content: "Simple response",
        })}
      />,
    );
    // The font-mono div only appears when there are tool events or cost
    expect(container.querySelector(".font-mono")).toBeNull();
  });
});
