/**
 * Manages the Clarity Agent FastAPI backend as a child process.
 *
 * Spawns the launcher server (`clarity.py web --port <port>`) which
 * handles multi-project routing internally. When `uv` is available
 * and `clarity.useUv` is enabled, uses `uv run` for dependency
 * management instead of pip.
 */

import { ChildProcess, execSync, spawn } from "child_process";
import * as http from "http";
import * as net from "net";
import * as path from "path";
import * as vscode from "vscode";

export type BackendState = "stopped" | "starting" | "running" | "error";

export interface BackendManagerEvents {
  onStateChange: (state: BackendState) => void;
  onLog: (message: string) => void;
}

export class BackendManager {
  private process: ChildProcess | null = null;
  private _state: BackendState = "stopped";
  private _port = 0;
  private stderrBuffer = "";
  private outputChannel: vscode.OutputChannel;
  private events: BackendManagerEvents;
  private depsInstalled = false;
  private _uvAvailable: boolean | undefined;

  constructor(
    private readonly clarityAgentDir: string,
    events: BackendManagerEvents,
  ) {
    this.outputChannel = vscode.window.createOutputChannel("Clarity Agent");
    this.events = events;
  }

  get state(): BackendState {
    return this._state;
  }

  get port(): number {
    return this._port;
  }

  get baseUrl(): string {
    return `http://127.0.0.1:${this._port}`;
  }

  private setState(state: BackendState): void {
    this._state = state;
    this.events.onStateChange(state);
  }

  /**
   * Check whether `uv` is available on the system.
   */
  private get uvAvailable(): boolean {
    if (this._uvAvailable === undefined) {
      const config = vscode.workspace.getConfiguration("clarity");
      const useUv = config.get<boolean>("useUv", true);
      if (!useUv) {
        this._uvAvailable = false;
        return false;
      }
      try {
        execSync("uv --version", { timeout: 5_000, stdio: "pipe" });
        this._uvAvailable = true;
      } catch {
        this._uvAvailable = false;
      }
    }
    return this._uvAvailable;
  }

  /**
   * Start the backend launcher server.
   *
   * When a projectDir is provided, it is registered and activated
   * via the launcher API after the server starts.
   */
  async start(projectDir?: string): Promise<void> {
    if (this._state === "running" || this._state === "starting") {
      return;
    }

    this.setState("starting");
    this.stderrBuffer = "";
    this.outputChannel.appendLine(
      `Starting Clarity backend${projectDir ? ` for: ${projectDir}` : " (launcher mode)"}`,
    );

    // Ensure dependencies are installed
    if (!this.depsInstalled) {
      const depsOk = await this.ensureDependencies();
      if (!depsOk) {
        this.setState("error");
        return;
      }
      this.depsInstalled = true;
    }

    try {
      this._port = await this.findFreePort();
      this.outputChannel.appendLine(`Using port: ${this._port}`);

      const { cmd, args } = this.buildSpawnCommand(projectDir);
      this.outputChannel.appendLine(`Command: ${cmd} ${args.join(" ")}`);

      this.process = spawn(cmd, args, {
        cwd: this.clarityAgentDir,
        env: {
          ...process.env,
          PYTHONPATH: path.join(this.clarityAgentDir, "src"),
        },
        stdio: ["ignore", "pipe", "pipe"],
      });

      this.process.stdout?.on("data", (data: Buffer) => {
        const text = data.toString().trim();
        if (text) {
          this.outputChannel.appendLine(text);
          this.events.onLog(text);
        }
      });

      this.process.stderr?.on("data", (data: Buffer) => {
        const text = data.toString().trim();
        if (text) {
          this.stderrBuffer += text + "\n";
          this.outputChannel.appendLine(`[stderr] ${text}`);
          this.events.onLog(text);
        }
      });

      this.process.on("exit", (code, signal) => {
        this.outputChannel.appendLine(
          `Backend exited (code=${code}, signal=${signal})`,
        );
        this.process = null;
        if (this._state !== "stopped") {
          this.setState("error");
        }
      });

      this.process.on("error", (err) => {
        this.outputChannel.appendLine(`Backend process error: ${err.message}`);
        this.process = null;
        this.setState("error");
      });

      const ready = await this.waitForServer(30_000);
      if (ready) {
        this.setState("running");
        this.outputChannel.appendLine("Backend is ready.");

        // If a project dir was given, activate it via the launcher API
        if (projectDir) {
          await this.activateProject(projectDir);
        }

        // Apply model overrides from VS Code settings
        await this.applyModelOverrides();
      } else {
        this.outputChannel.appendLine("Backend failed to start within timeout.");

        if (
          this.stderrBuffer.includes("ModuleNotFoundError") ||
          this.stderrBuffer.includes("ImportError") ||
          this.stderrBuffer.includes("No module named")
        ) {
          this.outputChannel.appendLine(
            "Detected missing Python dependencies. Attempting install...",
          );
          this.stop();
          this.depsInstalled = false;
          await this.start(projectDir);
          return;
        }

        this.handleStartupError();
        this.stop();
        this.setState("error");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      this.outputChannel.appendLine(`Failed to start backend: ${msg}`);
      this.setState("error");
    }
  }

  /**
   * Stop the backend server.
   */
  stop(): void {
    if (this.process) {
      this.outputChannel.appendLine("Stopping Clarity backend...");
      this.process.kill("SIGTERM");
      const p = this.process;
      setTimeout(() => {
        if (p && !p.killed) {
          p.kill("SIGKILL");
        }
      }, 5_000);
      this.process = null;
    }
    this.setState("stopped");
  }

  /**
   * Restart the backend, optionally for a different project.
   */
  async restart(projectDir?: string): Promise<void> {
    this.stop();
    await new Promise((resolve) => setTimeout(resolve, 500));
    await this.start(projectDir);
  }

  /**
   * Show the output channel.
   */
  showOutput(): void {
    this.outputChannel.show();
  }

  dispose(): void {
    this.stop();
    this.outputChannel.dispose();
  }

  /**
   * Make an HTTP request to the running backend.
   */
  async apiGet(path: string): Promise<string> {
    return new Promise((resolve, reject) => {
      const url = `${this.baseUrl}${path}`;
      const req = http.get(url, { timeout: 10_000 }, (res) => {
        let body = "";
        res.on("data", (chunk: Buffer) => (body += chunk.toString()));
        res.on("end", () => {
          if (res.statusCode === 200) {
            resolve(body);
          } else {
            reject(new Error(`HTTP ${res.statusCode}: ${body}`));
          }
        });
      });
      req.on("error", reject);
      req.on("timeout", () => {
        req.destroy();
        reject(new Error("Request timed out"));
      });
    });
  }

  /**
   * Make an HTTP POST request to the running backend.
   */
  async apiPost(apiPath: string, data: Record<string, unknown> = {}): Promise<string> {
    return new Promise((resolve, reject) => {
      const body = JSON.stringify(data);
      const url = new URL(`${this.baseUrl}${apiPath}`);
      const options: http.RequestOptions = {
        hostname: url.hostname,
        port: url.port,
        path: url.pathname,
        method: "POST",
        timeout: 10_000,
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(body),
        },
      };
      const req = http.request(options, (res) => {
        let respBody = "";
        res.on("data", (chunk: Buffer) => (respBody += chunk.toString()));
        res.on("end", () => {
          if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
            resolve(respBody);
          } else {
            reject(new Error(`HTTP ${res.statusCode}: ${respBody}`));
          }
        });
      });
      req.on("error", reject);
      req.on("timeout", () => {
        req.destroy();
        reject(new Error("Request timed out"));
      });
      req.write(body);
      req.end();
    });
  }

  // -- Private helpers --

  /**
   * Build the spawn command and arguments.
   */
  private buildSpawnCommand(projectDir?: string): { cmd: string; args: string[] } {
    const clarityPy = path.join(this.clarityAgentDir, "clarity.py");
    const baseArgs = ["web", "--port", String(this._port), "--host", "127.0.0.1"];

    if (projectDir) {
      baseArgs.splice(1, 0, projectDir);
    }

    if (this.uvAvailable) {
      return {
        cmd: "uv",
        args: ["run", "--extra", "web", "--directory", this.clarityAgentDir, "python", clarityPy, ...baseArgs],
      };
    }

    const pythonPath = this.getPythonPath();
    return { cmd: pythonPath, args: [clarityPy, ...baseArgs] };
  }

  /**
   * Activate a project in the launcher.
   */
  private async activateProject(projectDir: string): Promise<void> {
    try {
      const name = path.basename(projectDir);
      // Register the project
      await this.apiPost("/api/projects", { name, path: projectDir });
      // Activate it
      await this.apiPost(`/api/projects/${encodeURIComponent(name)}/activate`);
      this.outputChannel.appendLine(`Activated project: ${name}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      this.outputChannel.appendLine(`Note: could not activate project via launcher API: ${msg}`);
    }
  }

  /**
   * Apply model overrides from VS Code settings.
   */
  private async applyModelOverrides(): Promise<void> {
    const config = vscode.workspace.getConfiguration("clarity");
    const provider = config.get<string>("provider", "");
    const model = config.get<string>("model", "");

    if (!provider && !model) {
      return;
    }

    try {
      const data: Record<string, string> = {};
      if (provider) {
        data.provider = provider;
      }
      if (model) {
        data.model = model;
      }
      await this.apiPost("/api/model-profile/override", data);
      this.outputChannel.appendLine(
        `Applied model overrides: provider=${provider || "(default)"}, model=${model || "(default)"}`,
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      this.outputChannel.appendLine(`Note: could not apply model overrides: ${msg}`);
    }
  }

  /**
   * Parse startup errors and show actionable messages.
   */
  private handleStartupError(): void {
    const stderr = this.stderrBuffer;

    if (stderr.includes("No such file or directory") && stderr.includes("python")) {
      vscode.window
        .showErrorMessage(
          "Python was not found on your PATH. Install Python 3.12+ or set 'clarity.pythonPath' in settings.",
          "Open Settings",
          "Show Logs",
        )
        .then((choice) => {
          if (choice === "Open Settings") {
            vscode.commands.executeCommand(
              "workbench.action.openSettings",
              "clarity.pythonPath",
            );
          } else if (choice === "Show Logs") {
            this.showOutput();
          }
        });
      return;
    }

    if (stderr.includes("uv") && stderr.includes("not found")) {
      vscode.window
        .showErrorMessage(
          "uv was not found. Install uv (https://docs.astral.sh/uv/) or set 'clarity.useUv' to false.",
          "Open Settings",
          "Show Logs",
        )
        .then((choice) => {
          if (choice === "Open Settings") {
            vscode.commands.executeCommand(
              "workbench.action.openSettings",
              "clarity.useUv",
            );
          } else if (choice === "Show Logs") {
            this.showOutput();
          }
        });
      return;
    }

    if (stderr.includes("Address already in use")) {
      vscode.window
        .showErrorMessage(
          `Port ${this._port} is already in use. Set 'clarity.port' to 0 for automatic port selection.`,
          "Open Settings",
          "Show Logs",
        )
        .then((choice) => {
          if (choice === "Open Settings") {
            vscode.commands.executeCommand(
              "workbench.action.openSettings",
              "clarity.port",
            );
          } else if (choice === "Show Logs") {
            this.showOutput();
          }
        });
      return;
    }

    // Generic error
    vscode.window
      .showErrorMessage(
        "The Clarity backend failed to start. Check the output panel for details.",
        "Show Logs",
        "Retry",
      )
      .then((choice) => {
        if (choice === "Show Logs") {
          this.showOutput();
        } else if (choice === "Retry") {
          vscode.commands.executeCommand("clarity.restart");
        }
      });
  }

  /**
   * Check for and install missing Python dependencies.
   */
  private async ensureDependencies(): Promise<boolean> {
    if (this.uvAvailable) {
      // When using uv, the spawn command includes --extra web which
      // triggers automatic dependency resolution. Just verify the
      // project directory looks valid — don't run uv sync here as it
      // can conflict with an activated .venv in the user's terminal.
      this.outputChannel.appendLine(
        "Using uv — dependencies will be resolved automatically on spawn.",
      );
      return true;
    }

    // Fallback: pip-based installation
    const pythonPath = this.getPythonPath();

    try {
      execSync(
        `${pythonPath} -c "import fastapi; import uvicorn; import prompt_toolkit"`,
        {
          cwd: this.clarityAgentDir,
          env: {
            ...process.env,
            PYTHONPATH: path.join(this.clarityAgentDir, "src"),
          },
          timeout: 15_000,
          stdio: "pipe",
        },
      );
      this.outputChannel.appendLine("Python dependencies are available.");
      return true;
    } catch {
      // Dependencies missing
    }

    this.outputChannel.appendLine("Python dependencies not found. Installing...");

    const choice = await vscode.window.showInformationMessage(
      "Clarity Agent needs to install Python dependencies (fastapi, uvicorn, etc.). Install now?",
      { modal: true },
      "Install",
      "Cancel",
    );

    if (choice !== "Install") {
      this.outputChannel.appendLine("User declined dependency installation.");
      return false;
    }

    return vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Installing Clarity Agent dependencies...",
        cancellable: false,
      },
      async (progress) => {
        try {
          progress.report({ message: "Running pip install..." });

          const pyprojectDir = this.clarityAgentDir;
          execSync(
            `${pythonPath} -m pip install --quiet "${pyprojectDir}[web]"`,
            {
              cwd: this.clarityAgentDir,
              env: {
                ...process.env,
                PYTHONPATH: path.join(this.clarityAgentDir, "src"),
              },
              timeout: 300_000,
              stdio: "pipe",
            },
          );

          this.outputChannel.appendLine("Dependencies installed successfully.");
          vscode.window.showInformationMessage(
            "Clarity Agent dependencies installed successfully!",
          );
          return true;
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          this.outputChannel.appendLine(`Failed to install dependencies: ${msg}`);
          vscode.window.showErrorMessage(
            `Failed to install dependencies: ${msg}\n\nTry running manually: ${pythonPath} -m pip install "${this.clarityAgentDir}[web]"`,
          );
          return false;
        }
      },
    );
  }

  private getPythonPath(): string {
    const config = vscode.workspace.getConfiguration("clarity");
    const configured = config.get<string>("pythonPath", "");
    if (configured) {
      return configured;
    }
    return process.platform === "win32" ? "python" : "python3";
  }

  private findFreePort(): Promise<number> {
    const config = vscode.workspace.getConfiguration("clarity");
    const configured = config.get<number>("port", 0);
    if (configured > 0) {
      return Promise.resolve(configured);
    }

    return new Promise((resolve, reject) => {
      const server = net.createServer();
      server.listen(0, "127.0.0.1", () => {
        const addr = server.address();
        if (addr && typeof addr === "object") {
          const port = addr.port;
          server.close(() => resolve(port));
        } else {
          server.close(() => reject(new Error("Could not find free port")));
        }
      });
      server.on("error", reject);
    });
  }

  private waitForServer(timeoutMs: number): Promise<boolean> {
    const start = Date.now();
    const url = `http://127.0.0.1:${this._port}/api/session`;

    return new Promise((resolve) => {
      const poll = () => {
        if (Date.now() - start > timeoutMs) {
          resolve(false);
          return;
        }

        if (this.process === null || this.process.exitCode !== null) {
          resolve(false);
          return;
        }

        const req = http.get(url, { timeout: 2000 }, (res) => {
          if (res.statusCode === 200) {
            res.resume();
            resolve(true);
          } else {
            res.resume();
            setTimeout(poll, 300);
          }
        });

        req.on("error", () => {
          setTimeout(poll, 300);
        });

        req.on("timeout", () => {
          req.destroy();
          setTimeout(poll, 300);
        });
      };

      poll();
    });
  }
}