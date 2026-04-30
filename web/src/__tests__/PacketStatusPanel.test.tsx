import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import PacketStatusPanel from "../components/PacketStatusPanel";
import type { PacketStatusData } from "../types";

// Mock the API client
vi.mock("../api/client", () => ({
  getPacketStatus: vi.fn(),
}));

import { getPacketStatus } from "../api/client";
const mockGetPacketStatus = vi.mocked(getPacketStatus);

function renderPanel() {
  return render(
    <MemoryRouter>
      <PacketStatusPanel />
    </MemoryRouter>,
  );
}

const SAMPLE_DATA: PacketStatusData = {
  report: {
    protocol_dir: "/tmp/project/.clarity-protocol",
    documents: {
      "goal/problem.md": {
        status: "current",
        content_hash: "abc123",
        dependencies: [],
        stale_because: [],
      },
      "solution/solution.md": {
        status: "stale",
        content_hash: "def456",
        dependencies: ["goal/problem.md"],
        stale_because: [
          { doc: "goal/problem.md", current_hash: "abc999", recorded_hash: "abc123" },
        ],
      },
      "failures/failures.md": {
        status: "missing",
        content_hash: null,
        dependencies: ["solution/solution.md"],
        stale_because: [],
      },
    },
    summary: {
      current: ["goal/problem.md"],
      stale: ["solution/solution.md"],
      empty: [],
      missing: ["failures/failures.md"],
      untracked: [],
    },
    mailboxes: [],
  },
  decisions: {},
  next_action: {
    action: "Update",
    document: "solution/solution.md",
    process: "solution-brainstorming",
    reason: "Dependencies have changed",
  },
  process_availability: [
    { process: "problem-clarification", status: "available", reason: "Refine the problem statement and goals" },
    { process: "solution-brainstorming", status: "recommended", reason: "solution/solution.md is stale" },
    { process: "failure-brainstorming", status: "unavailable", reason: "Requires goal/problem.md to have content" },
    { process: "decision-guidance", status: "available", reason: "Always available" },
  ],
};

describe("PacketStatusPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state initially", () => {
    mockGetPacketStatus.mockReturnValue(new Promise(() => {})); // never resolves
    renderPanel();
    expect(screen.getByText("Loading status...")).toBeInTheDocument();
  });

  it("renders staleness data with status badges", async () => {
    mockGetPacketStatus.mockResolvedValue(SAMPLE_DATA);
    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("Packet Status")).toBeInTheDocument();
    });

    // Status badges in summary
    expect(screen.getByText("Current: 1")).toBeInTheDocument();
    expect(screen.getByText("Stale: 1")).toBeInTheDocument();
    expect(screen.getByText("Missing: 1")).toBeInTheDocument();
  });

  it("renders the next action card", async () => {
    mockGetPacketStatus.mockResolvedValue(SAMPLE_DATA);
    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("Recommended Next Step")).toBeInTheDocument();
    });
    // The action card renders "<strong>Update</strong>: document — run process"
    expect(screen.getByText("Update")).toBeInTheDocument();
    expect(screen.getByText(/run solution-brainstorming/)).toBeInTheDocument();
  });

  it("renders document table with clickable document names", async () => {
    mockGetPacketStatus.mockResolvedValue(SAMPLE_DATA);
    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("Packet Status")).toBeInTheDocument();
    });

    // Documents appear as clickable buttons in the table
    const buttons = screen.getAllByRole("button");
    const docButtons = buttons.filter((b) =>
      ["goal/problem.md", "solution/solution.md", "failures/failures.md"].includes(
        b.textContent ?? "",
      ),
    );
    expect(docButtons).toHaveLength(3);
  });

  it("shows stale_because reason", async () => {
    mockGetPacketStatus.mockResolvedValue(SAMPLE_DATA);
    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("goal/problem.md changed")).toBeInTheDocument();
    });
  });

  it("shows error for missing protocol directory", async () => {
    mockGetPacketStatus.mockRejectedValue(new Error("404: Not found"));
    renderPanel();

    await waitFor(() => {
      expect(
        screen.getByText("No .clarity-protocol/ directory found."),
      ).toBeInTheDocument();
    });
  });

  it("shows generic error for other failures", async () => {
    mockGetPacketStatus.mockRejectedValue(new Error("500: Server error"));
    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("Error: 500: Server error")).toBeInTheDocument();
    });
  });

  it("does not render empty summary badges", async () => {
    mockGetPacketStatus.mockResolvedValue(SAMPLE_DATA);
    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("Packet Status")).toBeInTheDocument();
    });

    // "Empty: 0" and "Untracked: 0" should not appear
    expect(screen.queryByText(/Empty:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Untracked:/)).not.toBeInTheDocument();
  });
});
