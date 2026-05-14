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

import { BackendManager, BackendState } from "./backendManager";
import { ProtocolTreeProvider } from "./protocolTreeProvider";
import { ClarityStatusBar } from "./statusBar";
import { ClarityViewProvider } from "./webviewViewProvider";

let backend: BackendManager | undefined;
let statusBar: ClarityStatusBar | undefined;
let sidebarProvider: ClarityViewProvider | undefined;
let protocolTree: ProtocolTreeProvider | undefined;

/**
 * Resolve the clarity-agent directory.
 *
 * Priority:
 * 1. User setting `clarity.agentDir` (override for developers)
 * 2. Bundled copy inside the extension (bundled/)
 * 3. Development mode — extension is at <repo>/vscode-extension/
 */
function resolveAgentDir(): string | undefined {
  const config = vscode.workspace.getConfiguration("clarity");
  const configured = config.get<string>("agentDir", "");
  if (configured && fs.existsSync(path.join(configured, "clarity.py"))) {
    return configured;
  }

  const extRoot = path.resolve(__dirname, "..");
  const bundledDir = path.join(extRoot, "bundled");
  if (
    fs.existsSync(path.join(bundledDir, "clarity.py")) &&
    fs.existsSync(path.join(bundledDir, "src", "clarity_agent"))
  ) {
    return bundledDir;
  }

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

/**
 * Ensure the backend is started and return it, or undefined on failure.
 */
async function ensureBackend(): Promise<BackendManager | undefined> {
  const agentDir = resolveAgentDir();
  if (!agentDir) {
    vscode.window.showErrorMessage(
      "Cannot find the Clarity Agent files. " +
        "Set 'clarity.agentDir' in settings to point to a clarity-agent clone.",
    );
    return undefined;
  }

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

  if (backend.state !== "running") {
    const projectDir = getProjectDir();
    sidebarProvider?.showStarting();
    await backend.start(projectDir);

    if (backend.state === "running") {
      sidebarProvider?.updateUrl(backend.baseUrl);

      // Check for updates after startup
      checkForUpdates();
    } else {
      sidebarProvider?.showError(
        "The Clarity backend failed to start. Check the Clarity Agent output panel for details.",
      );
      backend.showOutput();
      return undefined;
    }
  }

  return backend;
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
    await cmdOpenProject();
    return;
  }

  await startAndShow(agentDir, projectDir);
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

  await startAndShow(agentDir, uris[0].fsPath);
}

async function cmdDoctor(): Promise<void> {
  const agentDir = resolveAgentDir();
  if (!agentDir) {
    vscode.window.showErrorMessage("Cannot find the Clarity Agent files.");
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

  const projectDir = getProjectDir();
  await backend.restart(projectDir);

  if (backend.state === "running") {
    sidebarProvider?.updateUrl(backend.baseUrl);
  }
}

async function cmdSwitchProject(): Promise<void> {
  const b = await ensureBackend();
  if (!b) { return; }

  try {
    const resp = await b.apiGet("/api/projects");
    const data = JSON.parse(resp);
    const projects: Array<{ name: string; path: string; active: boolean }> =
      data.projects || [];

    if (projects.length === 0) {
      vscode.window.showInformationMessage("No projects registered yet.");
      return;
    }

    const items = projects.map((p) => ({
      label: p.active ? `$(check) ${p.name}` : p.name,
      description: p.path,
      name: p.name,
    }));

    const picked = await vscode.window.showQuickPick(items, {
      placeHolder: "Select a project to activate",
    });

    if (picked) {
      await b.apiPost(`/api/projects/${encodeURIComponent(picked.name)}/activate`);
      vscode.window.showInformationMessage(`Activated project: ${picked.name}`);
      sidebarProvider?.updateUrl(b.baseUrl);
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    vscode.window.showErrorMessage(`Failed to switch project: ${msg}`);
  }
}

async function cmdSetup(): Promise<void> {
  const b = await ensureBackend();
  if (!b) { return; }

  // Open the web UI setup page in a new webview panel
  const panel = vscode.window.createWebviewPanel(
    "clarity.setup",
    "Clarity Setup Wizard",
    vscode.ViewColumn.One,
    { enableScripts: true, retainContextWhenHidden: true },
  );

  panel.webview.html = `<!DOCTYPE html>
<html style="height:100%;margin:0;padding:0;">
<head><meta charset="UTF-8"></head>
<body style="height:100%;margin:0;padding:0;overflow:hidden;">
<iframe src="${b.baseUrl}/setup" style="width:100%;height:100%;border:none;"
  sandbox="allow-scripts allow-same-origin allow-forms allow-popups"></iframe>
</body></html>`;
}

async function cmdSelectModel(): Promise<void> {
  const b = await ensureBackend();
  if (!b) { return; }

  try {
    const resp = await b.apiGet("/api/model-profile");
    const profile = JSON.parse(resp);

    const currentProvider = profile.provider || "unknown";
    const currentModel = profile.model || "unknown";

    const provider = await vscode.window.showInputBox({
      prompt: "LLM Provider",
      value: currentProvider,
      placeHolder: "anthropic, openai, azure, claude-sdk, google, github-copilot",
    });

    if (provider === undefined) { return; }

    const model = await vscode.window.showInputBox({
      prompt: "Model name (leave empty for provider default)",
      value: currentModel !== "unknown" ? currentModel : "",
    });

    if (model === undefined) { return; }

    const data: Record<string, string> = {};
    if (provider) { data.provider = provider; }
    if (model) { data.model = model; }

    await b.apiPost("/api/model-profile/override", data);
    vscode.window.showInformationMessage(
      `Model set to ${provider || "default"}/${model || "default"}`,
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    vscode.window.showErrorMessage(`Failed to set model: ${msg}`);
  }
}

async function cmdGeneratePacket(): Promise<void> {
  const b = await ensureBackend();
  if (!b) { return; }

  try {
    const optResp = await b.apiGet("/api/packet/options");
    const options = JSON.parse(optResp);

    const formats: string[] = (options.formats || ["markdown", "docx"]);
    const format = await vscode.window.showQuickPick(formats, {
      placeHolder: "Select output format",
    });

    if (!format) { return; }

    const resp = await b.apiPost("/api/packet/generate", { format });

    if (format === "markdown") {
      const doc = await vscode.workspace.openTextDocument({
        content: resp,
        language: "markdown",
      });
      await vscode.window.showTextDocument(doc);
    } else {
      vscode.window.showInformationMessage(
        `Packet generated (${resp.length} bytes). Use the web UI to download binary formats.`,
      );
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    vscode.window.showErrorMessage(`Failed to generate packet: ${msg}`);
  }
}

async function cmdListProcesses(): Promise<void> {
  const b = await ensureBackend();
  if (!b) { return; }

  try {
    const resp = await b.apiGet("/api/processes");
    const data = JSON.parse(resp);
    const processes: Array<{ name: string; display_name: string; one_liner: string }> =
      data.processes || [];

    const items = processes.map((p) => ({
      label: p.display_name || p.name,
      description: p.one_liner || "",
      processName: p.name,
    }));

    const picked = await vscode.window.showQuickPick(items, {
      placeHolder: "Select a process to start",
    });

    if (picked) {
      // Focus the sidebar and let the web UI handle the process
      sidebarProvider?.reveal();
      vscode.window.showInformationMessage(
        `Starting process: ${picked.label}. Switch to the Clarity sidebar to interact.`,
      );
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    vscode.window.showErrorMessage(`Failed to list processes: ${msg}`);
  }
}

async function cmdViewTranscripts(): Promise<void> {
  const b = await ensureBackend();
  if (!b) { return; }

  try {
    const resp = await b.apiGet("/api/transcripts");
    const data = JSON.parse(resp);
    const transcripts: Array<{ name: string; timestamp?: string }> =
      data.transcripts || [];

    if (transcripts.length === 0) {
      vscode.window.showInformationMessage("No transcripts found.");
      return;
    }

    const items = transcripts.map((t) => ({
      label: t.name,
      description: t.timestamp || "",
    }));

    const picked = await vscode.window.showQuickPick(items, {
      placeHolder: "Select a transcript to view",
    });

    if (picked) {
      const content = await b.apiGet(`/api/transcripts/${encodeURIComponent(picked.label)}`);
      const parsed = JSON.parse(content);
      const doc = await vscode.workspace.openTextDocument({
        content: parsed.content || content,
        language: "markdown",
      });
      await vscode.window.showTextDocument(doc);
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    vscode.window.showErrorMessage(`Failed to load transcripts: ${msg}`);
  }
}

async function cmdSendFeedback(): Promise<void> {
  const b = await ensureBackend();
  if (!b) { return; }

  const message = await vscode.window.showInputBox({
    prompt: "Enter your feedback about Clarity Agent",
    placeHolder: "What's working well? What could be improved?",
  });

  if (!message) { return; }

  try {
    await b.apiPost("/api/feedback", { message, source: "vscode-extension" });
    vscode.window.showInformationMessage("Feedback sent. Thank you!");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    vscode.window.showErrorMessage(`Failed to send feedback: ${msg}`);
  }
}

async function cmdConfigureMcp(): Promise<void> {
  const agentDir = resolveAgentDir();
  if (!agentDir) {
    vscode.window.showErrorMessage("Cannot find the Clarity Agent files.");
    return;
  }

  const projectDir = getProjectDir();
  if (!projectDir) {
    vscode.window.showErrorMessage("No workspace folder open.");
    return;
  }

  const mcpConfigDir = path.join(projectDir, ".vscode");
  const mcpConfigPath = path.join(mcpConfigDir, "mcp.json");

  const mcpConfig = {
    mcpServers: {
      "clarity-agent": {
        command: "uv",
        args: [
          "run",
          "--extra",
          "mcp",
          "--directory",
          agentDir,
          "python",
          "-m",
          "clarity_agent.mcp",
        ],
        env: {
          CLARITY_PROJECT_DIR: "${workspaceFolder}",
        },
      },
    },
  };

  if (!fs.existsSync(mcpConfigDir)) {
    fs.mkdirSync(mcpConfigDir, { recursive: true });
  }

  // Merge with existing config if present
  let existing: Record<string, unknown> = {};
  if (fs.existsSync(mcpConfigPath)) {
    try {
      existing = JSON.parse(fs.readFileSync(mcpConfigPath, "utf-8"));
    } catch {
      // Overwrite invalid JSON
    }
  }

  const merged = {
    ...existing,
    mcpServers: {
      ...(existing.mcpServers as Record<string, unknown> || {}),
      ...mcpConfig.mcpServers,
    },
  };

  fs.writeFileSync(mcpConfigPath, JSON.stringify(merged, null, 2), "utf-8");

  const doc = await vscode.workspace.openTextDocument(mcpConfigPath);
  await vscode.window.showTextDocument(doc);
  vscode.window.showInformationMessage("MCP server configuration written to .vscode/mcp.json");
}

// -----------------------------------------------------------------------
// Update checker
// -----------------------------------------------------------------------

async function checkForUpdates(): Promise<void> {
  if (!backend || backend.state !== "running") { return; }

  try {
    const resp = await backend.apiGet("/api/update-check");
    const data = JSON.parse(resp);

    if (data.update_available) {
      const choice = await vscode.window.showInformationMessage(
        `Clarity Agent update available: ${data.latest_version || "new version"}`,
        "Update Now",
        "Dismiss",
      );

      if (choice === "Update Now") {
        await backend.apiPost("/api/update/run");
        vscode.window.showInformationMessage("Update complete. Restarting backend...");
        await backend.apiPost("/api/update/restart");
      }
    }
  } catch {
    // Silently ignore update check failures
  }
}

// -----------------------------------------------------------------------
// Core logic
// -----------------------------------------------------------------------

async function startAndShow(
  agentDir: string,
  projectDir: string,
): Promise<void> {
  if (!backend) {
    backend = new BackendManager(agentDir, {
      onStateChange: (state: BackendState) => {
        statusBar?.update(state);
      },
      onLog: (_message: string) => {},
    });
  }

  sidebarProvider?.reveal();

  const currentState = backend.state;
  if (currentState !== "running") {
    sidebarProvider?.showStarting();

    await backend.start(projectDir);

    const newState: BackendState = backend.state;
    if (newState === "running") {
      sidebarProvider?.updateUrl(backend.baseUrl);
      checkForUpdates();
    } else {
      sidebarProvider?.showError(
        "The Clarity backend failed to start. Check the Clarity Agent output panel for details.",
      );
      backend.showOutput();
    }
  } else {
    sidebarProvider?.updateUrl(backend.baseUrl);
  }
}

// -----------------------------------------------------------------------
// Lifecycle
// -----------------------------------------------------------------------

export function activate(context: vscode.ExtensionContext): void {
  statusBar = new ClarityStatusBar();
  context.subscriptions.push({ dispose: () => statusBar?.dispose() });

  sidebarProvider = new ClarityViewProvider();
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      ClarityViewProvider.viewId,
      sidebarProvider,
      { webviewOptions: { retainContextWhenHidden: true } },
    ),
  );

  // Protocol tree view
  protocolTree = new ProtocolTreeProvider();
  context.subscriptions.push(
    vscode.window.createTreeView("clarity.protocolTree", {
      treeDataProvider: protocolTree,
      showCollapseAll: true,
    }),
  );

  context.subscriptions.push(
    sidebarProvider.onMessage((msg) => {
      if (msg.command === "start") {
        cmdOpen();
      }
    }),
  );

  // Register all commands
  context.subscriptions.push(
    vscode.commands.registerCommand("clarity.open", cmdOpen),
    vscode.commands.registerCommand("clarity.openProject", cmdOpenProject),
    vscode.commands.registerCommand("clarity.doctor", cmdDoctor),
    vscode.commands.registerCommand("clarity.restart", cmdRestart),
    vscode.commands.registerCommand("clarity.switchProject", cmdSwitchProject),
    vscode.commands.registerCommand("clarity.setup", cmdSetup),
    vscode.commands.registerCommand("clarity.selectModel", cmdSelectModel),
    vscode.commands.registerCommand("clarity.generatePacket", cmdGeneratePacket),
    vscode.commands.registerCommand("clarity.listProcesses", cmdListProcesses),
    vscode.commands.registerCommand("clarity.viewTranscripts", cmdViewTranscripts),
    vscode.commands.registerCommand("clarity.sendFeedback", cmdSendFeedback),
    vscode.commands.registerCommand("clarity.configureMcp", cmdConfigureMcp),
    vscode.commands.registerCommand("clarity.refreshProtocol", () => {
      protocolTree?.refresh();
    }),
    vscode.commands.registerCommand("clarity.openProtocolDocument", async (docPath: string) => {
      const b = backend;
      if (!b || b.state !== "running") { return; }
      try {
        const resp = await b.apiGet(`/api/protocol/document/${encodeURIComponent(docPath)}`);
        const data = JSON.parse(resp);
        const doc = await vscode.workspace.openTextDocument({
          content: data.content || resp,
          language: "markdown",
        });
        await vscode.window.showTextDocument(doc, { preview: true });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        vscode.window.showErrorMessage(`Failed to open document: ${msg}`);
      }
    }),
  );

  // Sync workspace folders as projects when they change
  context.subscriptions.push(
    vscode.workspace.onDidChangeWorkspaceFolders(async () => {
      if (backend && backend.state === "running") {
        const folders = vscode.workspace.workspaceFolders || [];
        for (const folder of folders) {
          try {
            await backend.apiPost("/api/projects", {
              name: folder.name,
              path: folder.uri.fsPath,
            });
          } catch {
            // Ignore registration errors for existing projects
          }
        }
      }
    }),
  );
}

export function deactivate(): void {
  backend?.dispose();
  backend = undefined;
  statusBar?.dispose();
  statusBar = undefined;
}