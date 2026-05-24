/**
 * Status bar item that shows the Clarity Agent backend state
 * and the active project name.
 */

import * as vscode from "vscode";
import type { BackendState } from "./backendManager";

const ICONS: Record<BackendState, string> = {
  stopped: "$(circle-slash)",
  starting: "$(loading~spin)",
  running: "$(check)",
  error: "$(error)",
};

const LABELS: Record<BackendState, string> = {
  stopped: "Clarity: Offline",
  starting: "Clarity: Starting...",
  running: "Clarity: Connected",
  error: "Clarity: Error",
};

const COLORS: Record<BackendState, string | undefined> = {
  stopped: undefined,
  starting: undefined,
  running: undefined,
  error: "statusBarItem.errorBackground",
};

export class ClarityStatusBar {
  private item: vscode.StatusBarItem;
  private _projectName = "";

  constructor() {
    this.item = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      100,
    );
    this.item.command = "clarity.open";
    this.update("stopped");
    this.item.show();
  }

  update(state: BackendState): void {
    const projectSuffix = this._projectName && state === "running"
      ? ` · ${this._projectName}`
      : "";
    this.item.text = `${ICONS[state]} ${LABELS[state]}${projectSuffix}`;
    const bg = COLORS[state];
    this.item.backgroundColor = bg
      ? new vscode.ThemeColor(bg)
      : undefined;
    this.item.tooltip =
      state === "running"
        ? "Click to open Clarity Agent"
        : state === "error"
          ? "Clarity backend encountered an error. Click to open."
          : "Clarity Agent";
  }

  setProjectName(name: string): void {
    this._projectName = name;
  }

  dispose(): void {
    this.item.dispose();
  }
}