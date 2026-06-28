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

  it("does not render tool events inline for assistant messages", () => {
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
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.queryByText(/read_file/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("tool-terminal")).not.toBeInTheDocument();
  });

  it("does not render tool-only assistant messages in the chat timeline", () => {
    const { container } = render(
      <ChatMessage
        message={makeMessage({
          role: "assistant",
          content: "",
          toolEvents: [
            { tool: "bash", detail: "npm run build" },
          ],
        })}
      />,
    );

    expect(screen.queryByText(/npm run build/)).not.toBeInTheDocument();
    expect(container.querySelector(".prose")).toBeNull();
    expect(screen.queryByText("Clarity")).not.toBeInTheDocument();
  });

  it("does not render usage inline for assistant messages", () => {
    render(
      <ChatMessage
        message={makeMessage({
          role: "assistant",
          content: "Result",
          costUsd: 0.0567,
        })}
      />,
    );
    expect(screen.getByText("Result")).toBeInTheDocument();
    expect(screen.queryByText("$0.0567")).not.toBeInTheDocument();
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
