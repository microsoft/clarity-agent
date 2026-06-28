import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import ToolLogPane from "../components/ToolLogPane";

const events = [
  { tool: "bash", detail: "npm run build" },
  { tool: "backend", detail: "chat backend ready" },
];

describe("ToolLogPane", () => {
  it("renders a glowing trigger when closed with unread log lines", () => {
    render(
      <ToolLogPane
        events={events}
        open={false}
        unread
        width={460}
        onOpenChange={() => {}}
        onWidthChange={() => {}}
      />,
    );

    expect(screen.getByTestId("log-pane-toggle")).toHaveAttribute("data-unread", "true");
    expect(screen.getByTestId("log-side-pane")).toHaveAttribute("data-open", "false");
    expect(screen.queryByText(/npm run build/)).not.toBeInTheDocument();
  });

  it("opens the split pane and stops marking the trigger unread", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const { rerender } = render(
      <ToolLogPane
        events={events}
        open={false}
        unread
        width={460}
        onOpenChange={onOpenChange}
        onWidthChange={() => {}}
      />,
    );

    await user.click(screen.getByTestId("log-pane-toggle"));
    expect(onOpenChange).toHaveBeenCalledWith(true);

    rerender(
      <ToolLogPane
        events={events}
        open
        unread={false}
        width={460}
        onOpenChange={onOpenChange}
        onWidthChange={() => {}}
      />,
    );

    expect(screen.queryByTestId("log-pane-toggle")).not.toBeInTheDocument();
    expect(screen.getByTestId("log-side-pane")).toHaveAttribute("data-open", "true");
    expect(screen.getByText("2 lines")).toBeInTheDocument();
    expect(screen.getByText(/npm run build/)).toBeInTheDocument();
  });

  it("resizes from the left edge while open", () => {
    const onWidthChange = vi.fn();
    render(
      <ToolLogPane
        events={events}
        open
        unread={false}
        width={460}
        onOpenChange={() => {}}
        onWidthChange={onWidthChange}
      />,
    );

    fireEvent.pointerDown(screen.getByTestId("log-pane-resize-handle"), {
      clientX: 700,
    });
    fireEvent.pointerMove(window, { clientX: 620 });

    expect(onWidthChange).toHaveBeenCalledWith(540);

    fireEvent.pointerUp(window);
  });

  it("does not render until log events exist", () => {
    const { container } = render(
      <ToolLogPane
        events={[]}
        open={false}
        unread={false}
        width={460}
        onOpenChange={() => {}}
        onWidthChange={() => {}}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
