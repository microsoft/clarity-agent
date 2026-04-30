/**
 * Manages the Clarity Agent FastAPI backend as a child process.
 *
 * Spawns `python clarity.py web <project-dir> --port <port>`, polls
 * until the server is ready, and provides start/stop/restart lifecycle.
 *
 * When dependencies are missing, automatically installs them via pip.
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
   * Start the backend server for a given project directory.
   */
  async start(projectDir: string): Promise<void> {
    if (this._state === "running" || this._state === "starting") {
      return;
    }

    this.setState("starting");
    this.stderrBuffer = "";
    this.outputChannel.appendLine(`Starting Clarity backend for: ${projectDir}`);

    // Ensure Python dependencies are installed
    if (!this.depsInstalled) {
      const depsOk = await this.ensureDependencies();
      if (!depsOk) {
        this.setState("error");
        return;
      }
      this.depsInstalled = true;
    }

    try {
      // Find a free port
      this._port = await this.findFreePort();
      this.outputChannel.appendLine(`Using port: ${this._port}`);

      // Resolve Python path
      const pythonPath = this.getPythonPath();
      const clarityPy = path.join(this.clarityAgentDir, "clarity.py");

      this.outputChannel.appendLine(
        `Command: ${pythonPath} ${clarityPy} web ${projectDir} --port ${this._port}`,
      );

      // Spawn the process
      this.process = spawn(
        pythonPath,
        [clarityPy, "web", projectDir, "--port", String(this._port), "--host", "127.0.0.1"],
        {
          cwd: this.clarityAgentDir,
          env: {
            ...process.env,
            // Ensure clarity_agent is importable
            PYTHONPATH: path.join(this.clarityAgentDir, "src"),
          },
          stdio: ["ignore", "pipe", "pipe"],
        },
      );

      // Pipe stdout/stderr to output channel
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

      // Wait for the server to respond
      const ready = await this.waitForServer(30_000);
      if (ready) {
        this.setState("running");
        this.outputChannel.appendLine("Backend is ready.");
      } else {
        this.outputChannel.appendLine("Backend failed to start within timeout.");

        // Check if it was a missing dependency issue
        if (this.stderrBuffer.includes("ModuleNotFoundError") ||
            this.stderrBuffer.includes("ImportError") ||
            this.stderrBuffer.includes("No module named")) {
          this.outputChannel.appendLine("Detected missing Python dependencies. Attempting install...");
          this.stop();
          this.depsInstalled = false;
          // Try again — ensureDependencies will run
          await this.start(projectDir);
          return;
        }

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
      // Force kill after 5 seconds
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
   * Restart the backend for a project directory.
   */
  async restart(projectDir: string): Promise<void> {
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

  // -- Private helpers --

  /**
   * Check for and install missing Python dependencies.
   * Returns true if dependencies are available, false if install failed.
   */
  private async ensureDependencies(): Promise<boolean> {
    const pythonPath = this.getPythonPath();

    // Quick check: can we import the critical modules?
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
      // Dependencies missing — install them
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

          // Install from the bundled pyproject.toml with the web extra
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
    // Try python3 first (macOS/Linux), fall back to python (Windows)
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

        // Check if the process has died
        if (this.process === null || this.process.exitCode !== null) {
          resolve(false);
          return;
        }

        const req = http.get(url, { timeout: 2000 }, (res) => {
          if (res.statusCode === 200) {
            // Consume the response body to free up the socket
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