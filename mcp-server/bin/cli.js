#!/usr/bin/env node
/**
 * Clarity Agent MCP Server — npx runner
 *
 * Spawns the Python MCP server (`python -m clarity_agent.mcp`) over stdio.
 * Handles Python discovery, uv/uvx fallback, and passes through all arguments.
 *
 * Usage:
 *   npx @clarity-agent/mcp --project-dir /path/to/project
 *   npx @clarity-agent/mcp --transport sse --port 8421
 */

const { spawn, execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

// ---------------------------------------------------------------------------
// Python resolution
// ---------------------------------------------------------------------------

/**
 * Try to run a command and return true if it succeeds.
 */
function commandExists(cmd) {
  try {
    execSync(`${cmd} --version`, { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

/**
 * Check if clarity_agent.mcp is importable by a Python interpreter.
 */
function clarityInstalled(pythonCmd) {
  try {
    execSync(`${pythonCmd} -c "import clarity_agent.mcp"`, { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

/**
 * Resolve the Python command to use.
 *
 * Priority:
 *   1. CLARITY_PYTHON env var
 *   2. python3 (if clarity_agent is importable)
 *   3. python  (if clarity_agent is importable)
 *   4. uvx clarity-agent (auto-installs via uv)
 */
function resolvePython() {
  // Explicit override
  const envPython = process.env.CLARITY_PYTHON;
  if (envPython) {
    return { cmd: envPython, args: ["-m", "clarity_agent.mcp"] };
  }

  // Try system Python with clarity-agent installed
  for (const py of ["python3", "python"]) {
    if (commandExists(py) && clarityInstalled(py)) {
      return { cmd: py, args: ["-m", "clarity_agent.mcp"] };
    }
  }

  // Try uvx (uv's package runner — like npx for Python)
  if (commandExists("uvx")) {
    return {
      cmd: "uvx",
      args: ["--from", "clarity-agent[mcp]", "python", "-m", "clarity_agent.mcp"],
    };
  }

  // Try uv run
  if (commandExists("uv")) {
    return {
      cmd: "uv",
      args: ["run", "--with", "clarity-agent[mcp]", "python", "-m", "clarity_agent.mcp"],
    };
  }

  return null;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  const resolved = resolvePython();

  if (!resolved) {
    process.stderr.write(
      "Error: Could not find Python with clarity-agent installed.\n\n" +
        "Install clarity-agent first:\n" +
        "  pip install clarity-agent[mcp]\n\n" +
        "Or install uv for automatic management:\n" +
        "  curl -LsSf https://astral.sh/uv/install.sh | sh\n"
    );
    process.exit(1);
  }

  // Pass through all CLI arguments after the script name
  const userArgs = process.argv.slice(2);
  const allArgs = [...resolved.args, ...userArgs];

  const child = spawn(resolved.cmd, allArgs, {
    stdio: "inherit",
    env: { ...process.env },
  });

  child.on("error", (err) => {
    process.stderr.write(`Failed to start clarity-agent MCP server: ${err.message}\n`);
    process.exit(1);
  });

  child.on("exit", (code) => {
    process.exit(code ?? 0);
  });

  // Forward signals so Ctrl+C cleanly shuts down the Python process
  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.on(signal, () => {
      child.kill(signal);
    });
  }
}

main();