/**
 * Clarity Agent VSCode Extension
 *
 * Entry point. Spawns the FastAPI backend as a child process and
 * displays the React SPA in a webview sidebar panel (Activity Bar).
 *
 * The extension bundles the entire clarity-agent Python source and
 * web frontend inside its own directory (bundled/), so it works on
 * machines that don't have clarity-agent installed separately.
 */

import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

import {
  BackendManager,
  BackendState,
  BackendStartTarget,
} from "./backendManager";
import { ClarityStatusBar } from "./statusBar";
import { ClarityViewProvider } from "./webviewViewProvider";

let backend: BackendManager | undefined;
let statusBar: ClarityStatusBar | undefined;
let sidebarProvider: ClarityViewProvider | undefined;

/**
 * Resolve the clarity-agent directory.
 *
 * Priority:
 * 1. User setting `clarity.agentDir` (override for developers)
 * 2. Bundled copy inside the extension (bundled/)
 * 3. Development mode — extension is at <repo>/vscode-extension/
 */
function resolveAgentDir(): string | undefined {
  // 1. Explicit user setting
  const config = vscode.workspace.getConfiguration("clarity");
  const configured = config.get<string>("agentDir", "");
  if (configured && fs.existsSync(path.join(configured, "clarity.py"))) {
    return configured;
  }

  // 2. Bundled copy: extension is at <ext>/out/extension.js,
  //    bundled dir is at <ext>/bundled/
  const extRoot = path.resolve(__dirname, "..");
  const bundledDir = path.join(extRoot, "bundled");
  if (
    fs.existsSync(path.join(bundledDir, "clarity.py")) &&
    fs.existsSync(path.join(bundledDir, "src", "clarity_agent"))
  ) {
    return bundledDir;
  }

  // 3. Development mode — extension is at <repo>/vscode-extension/
  const repoRoot = path.resolve(extRoot, "..");
  if (
    fs.existsSync(path.join(repoRoot, "clarity.py")) &&
    fs.existsSync(path.join(repoRoot, "src", "clarity_agent"))
  ) {
    return repoRoot;
  }

  return undefined;
}

/**
 * Get the project directory to use.
 */
function getProjectDir(): string | undefined {
  const folders = vscode.workspace.workspaceFolders;
  if (folders && folders.length > 0) {
    return folders[0].uri.fsPath;
  }
  return undefined;
}

// -----------------------------------------------------------------------
// Commands
// -----------------------------------------------------------------------

async function cmdOpen(): Promise<void> {
  const agentDir = resolveAgentDir();
  if (!agentDir) {
    vscode.window.showErrorMessage(
      "Cannot find the Clarity Agent files. " +
        "The extension may not have been packaged correctly, " +
        "or you can set 'clarity.agentDir' in settings to point to a clarity-agent clone.",
    );
    return;
  }

  const projectDir = getProjectDir();
  if (!projectDir) {
    await cmdOpenLauncher();
    return;
  }

  await startAndShow(agentDir, { mode: "project", projectDir });
}

async function cmdOpenProject(): Promise<void> {
  const agentDir = resolveAgentDir();
  if (!agentDir) {
    vscode.window.showErrorMessage(
      "Cannot find the Clarity Agent files. " +
        "Set 'clarity.agentDir' in settings to point to a clarity-agent clone.",
    );
    return;
  }

  const uris = await vscode.window.showOpenDialog({
    canSelectFolders: true,
    canSelectFiles: false,
    canSelectMany: false,
    openLabel: "Select Project Directory",
  });

  if (!uris || uris.length === 0) {
    return;
  }

  await startAndShow(agentDir, { mode: "project", projectDir: uris[0].fsPath });
}

async function cmdOpenLauncher(): Promise<void> {
  const agentDir = resolveAgentDir();
  if (!agentDir) {
    vscode.window.showErrorMessage(
      "Cannot find the Clarity Agent files. " +
        "Set 'clarity.agentDir' in settings to point to a clarity-agent clone.",
    );
    return;
  }

  await startAndShow(agentDir, { mode: "launcher" });
}

async function cmdDoctor(): Promise<void> {
  const agentDir = resolveAgentDir();
  if (!agentDir) {
    vscode.window.showErrorMessage(
      "Cannot find the Clarity Agent files.",
    );
    return;
  }

  const terminal = vscode.window.createTerminal({
    name: "Clarity Doctor",
    cwd: agentDir,
  });

  const config = vscode.workspace.getConfiguration("clarity");
  const pythonPath =
    config.get<string>("pythonPath", "") ||
    (process.platform === "win32" ? "python" : "python3");

  terminal.sendText(`${pythonPath} clarity.py doctor`);
  terminal.show();
}

async function cmdRestart(): Promise<void> {
  if (!backend) {
    vscode.window.showInformationMessage("No Clarity backend to restart.");
    return;
  }

  try {
    sidebarProvider?.showStarting();
    await backend.restart();
    if (backend.state === "running") {
      sidebarProvider?.updateUrl(backend.baseUrl);
    } else {
      sidebarProvider?.showError(
        "The Clarity backend failed to restart. Check the Clarity Agent output panel for details.",
      );
      backend.showOutput();
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    vscode.window.showErrorMessage(message);
  }
}

// -----------------------------------------------------------------------
// Core logic
// -----------------------------------------------------------------------

async function startAndShow(
  agentDir: string,
  target: BackendStartTarget,
): Promise<void> {
  if (!backend) {
    backend = new BackendManager(agentDir, {
      onStateChange: (state: BackendState) => {
        statusBar?.update(state);
      },
      onLog: (_message: string) => {
        // Could show notifications for critical errors
      },
    });
  }

  // Reveal the sidebar
  sidebarProvider?.reveal();

  sidebarProvider?.showStarting();

  await backend.start(target);

  // Re-check state after async start because dependency install or spawn can fail.
  const newState: BackendState = backend.state;
  if (newState === "running") {
    sidebarProvider?.updateUrl(backend.baseUrl);
  } else {
    sidebarProvider?.showError(
      "The Clarity backend failed to start. Check the Clarity Agent output panel for details.",
    );
    backend.showOutput();
  }
}

// -----------------------------------------------------------------------
// Lifecycle
// -----------------------------------------------------------------------

export function activate(context: vscode.ExtensionContext): void {
  // Status bar
  statusBar = new ClarityStatusBar();
  context.subscriptions.push({ dispose: () => statusBar?.dispose() });

  // Sidebar webview provider
  sidebarProvider = new ClarityViewProvider();
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      ClarityViewProvider.viewId,
      sidebarProvider,
      { webviewOptions: { retainContextWhenHidden: true } },
    ),
  );

  // Listen for messages from the sidebar webview (e.g., the "Start" button)
  context.subscriptions.push(
    sidebarProvider.onMessage((msg) => {
      if (msg.command === "start") {
        cmdOpen();
      }
    }),
  );

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand("clarity.open", cmdOpen),
    vscode.commands.registerCommand("clarity.openProject", cmdOpenProject),
    vscode.commands.registerCommand("clarity.openLauncher", cmdOpenLauncher),
    vscode.commands.registerCommand("clarity.doctor", cmdDoctor),
    vscode.commands.registerCommand("clarity.restart", cmdRestart),
  );
}

export function deactivate(): void {
  backend?.dispose();
  backend = undefined;
  statusBar?.dispose();
  statusBar = undefined;
}