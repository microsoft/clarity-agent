import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import ProjectSwitcher from "../components/ProjectSwitcher";
import type { ProjectEntry } from "../types";

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(),
  save: vi.fn(),
}));

vi.mock("../components/Layout", () => ({
  refreshRecentMenu: vi.fn().mockResolvedValue(undefined),
}));

const { getProjectsMock, removeProjectMock, activateProjectMock } = vi.hoisted(() => ({
  getProjectsMock: vi.fn(),
  removeProjectMock: vi.fn(),
  activateProjectMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  getProjects: getProjectsMock,
  removeProject: removeProjectMock,
  activateProject: activateProjectMock,
  createProject: vi.fn(),
}));

function makeProject(overrides: Partial<ProjectEntry> = {}): ProjectEntry {
  return {
    id: "abc12345",
    name: "alpha",
    path: "/home/u/alpha",
    last_opened: Date.now() / 1000,
    has_protocol: true,
    running: false,
    active: false,
    ...overrides,
  };
}

function renderSwitcher() {
  return render(
    <MemoryRouter>
      <ProjectSwitcher currentProject={undefined} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  getProjectsMock.mockReset();
  removeProjectMock.mockReset();
  activateProjectMock.mockReset();
});

describe("ProjectSwitcher remove flow", () => {
  it("shows a confirm strip when the trash button is clicked", async () => {
    getProjectsMock.mockResolvedValue({
      projects: [makeProject({ name: "alpha" }), makeProject({ name: "beta", id: "def67890", path: "/home/u/beta" })],
    });

    renderSwitcher();
    await waitFor(() => expect(screen.getByText("alpha")).toBeInTheDocument());

    const trash = screen.getByRole("button", { name: /remove alpha from list/i });
    await userEvent.click(trash);

    expect(
      screen.getByText((_, el) => el?.textContent === "Remove alpha from list?"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("calls removeProject and refreshes the list when confirmed", async () => {
    getProjectsMock
      .mockResolvedValueOnce({
        projects: [makeProject({ name: "alpha" }), makeProject({ name: "beta", id: "def67890", path: "/home/u/beta" })],
      })
      .mockResolvedValueOnce({
        projects: [makeProject({ name: "beta", id: "def67890", path: "/home/u/beta" })],
      });
    removeProjectMock.mockResolvedValue({ status: "removed" });

    renderSwitcher();
    await waitFor(() => expect(screen.getByText("alpha")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /remove alpha from list/i }));
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));

    await waitFor(() => {
      expect(removeProjectMock).toHaveBeenCalledWith("alpha");
    });
    await waitFor(() => {
      expect(screen.queryByText("alpha")).not.toBeInTheDocument();
    });
    expect(screen.getByText("beta")).toBeInTheDocument();
  });

  it("dismisses the confirm strip when Cancel is clicked", async () => {
    getProjectsMock.mockResolvedValue({
      projects: [makeProject({ name: "alpha" })],
    });

    renderSwitcher();
    await waitFor(() => expect(screen.getByText("alpha")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /remove alpha from list/i }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(removeProjectMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /remove alpha from list/i })).toBeInTheDocument();
  });
});

describe("ProjectSwitcher activation error handling", () => {
  it("shows a friendly message and refreshes the list when activation returns 410", async () => {
    getProjectsMock
      .mockResolvedValueOnce({
        projects: [makeProject({ name: "alpha" })],
      })
      .mockResolvedValueOnce({ projects: [] });
    activateProjectMock.mockRejectedValue(new Error("410: gone"));

    renderSwitcher();
    await waitFor(() => expect(screen.getByText("alpha")).toBeInTheDocument());

    await userEvent.click(screen.getByTitle("/home/u/alpha"));

    await waitFor(() => {
      expect(screen.getByText(/folder no longer exists/i)).toBeInTheDocument();
    });
  });
});
