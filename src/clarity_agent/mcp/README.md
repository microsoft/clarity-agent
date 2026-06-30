# Clarity Agent, Python MCP Server

This MCP server gives coding agents access to the clarity-agent process: problem clarification, failure brainstorming, decision recording, and review packet generation. It works with any MCP-capable tool (Claude Code, GitHub Copilot CLI, Cursor, Roo).

## Why

Coding agents write code but don't stop to ask whether the right thing is being built or what could go wrong. This server adds that capability with a small, focused tool surface designed for how coding agents actually work.

## Quick Start

### 1. Clone and install clarity-agent

```bash
git clone https://github.com/microsoft/clarity-agent.git
cd clarity-agent
uv pip install -e ".[mcp]"
```

Or with pip instead of uv:

```bash
pip install -e ".[mcp]"
```

### 2. Verify the server runs

```bash
python -m clarity_agent.mcp --help
```

### 3. Configure your project

**Option A: Automatic (recommended)**

```bash
clarity embed /path/to/your-project
```

This creates `.vscode/mcp.json`, the `.clarity-protocol/` directory, and an agent snippet in one step. It auto-detects whether you pip-installed clarity or are running from a uv-managed checkout, and generates the right MCP config accordingly.

If you move your clarity-agent installation after running embed in uv mode, re-run `clarity embed` to update the path in `.vscode/mcp.json`.

**Option B: Manual**

For **Claude Code** or **`gh copilot`**, create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "clarity-agent": {
      "command": "python",
      "args": ["-m", "clarity_agent.mcp", "--project-dir", "."]
    }
  }
}
```

For **VS Code** (Copilot Chat, Roo, Cursor), create `.vscode/mcp.json`:

```json
{
  "servers": {
    "clarity-agent": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "clarity_agent.mcp"],
      "env": {
        "CLARITY_PROJECT_DIR": "${workspaceFolder}"
      }
    }
  }
}
```

If you installed from a local clone with uv (not pip), use `uv run` with `--extra mcp` and `--directory` pointing to your clarity-agent checkout:

```json
{
  "servers": {
    "clarity-agent": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run", "--extra", "mcp",
        "--directory", "/path/to/clarity-agent",
        "python", "-m", "clarity_agent.mcp",
        "--project-dir", "${workspaceFolder}"
      ]
    }
  }
}
```

Replace `/path/to/clarity-agent` with the absolute path to your clarity-agent clone.

## Available Tools

The MCP server exposes 9 tools, designed around four moments in a coding agent's workflow:

### Before acting: check for conflicts

| Tool | Purpose |
|---|---|
| `check_decision` | Check whether a proposed change conflicts with existing decisions or requirements |

### Assess and navigate

| Tool | Purpose |
|---|---|
| `run_clarity` | Assess project state, get recommended next step with process guide inlined |
| `get_packet_status` | Check document staleness after completing significant work |

### Read, write, record

| Tool | Purpose |
|---|---|
| `read_protocol_document` | Read a protocol document |
| `write_protocol_document` | Write or update a protocol document (auto-records content hash) |
| `record_decision` | Record a structured decision with context, rationale, and alternatives |
| `record_failure` | Record a failure mode or risk |
| `record_suggestion` | Record a suggestion to update a project document |

### Share and review

| Tool | Purpose |
|---|---|
| `generate_packet` | Generate a shareable review packet from protocol content |

## How It Works

The server uses two directories:

- **project-dir**: your project, where `.clarity-protocol/` lives
- **agent-dir**: the installed clarity-agent package, where process guides and thinker guides live (resolved automatically)

When the agent calls `run_clarity()`, the server checks the project directory for `.clarity-protocol/`. If none exists, it returns the startup guide. If one exists, it checks document staleness, recommends the next process, and inlines the process guide content so the agent can follow it immediately.

`write_protocol_document` automatically records content hashes so the staleness tracker stays current without a separate `record_packet_status` call.

`generate_packet` takes a packet view name such as `complete`, `short`, or `engineer` and returns the selected packet as Markdown text. Use the web UI or CLI for file formats such as DOCX.

All read/write operations are scoped to the project directory with path traversal protection.

## Recommended Usage

The AGENTS.md snippet (inserted by `clarity embed`) tells your coding agent when to call each tool:

```markdown
Before making choices that would be expensive to reverse, call check_decision.
When starting work or returning after a break, call run_clarity.
After completing significant implementation, call get_packet_status.
Record significant choices with record_decision. Add risks with record_failure.
Generate shareable review packets with generate_packet.
```

**New project:**
1. Agent calls `run_clarity`, sees no protocol
2. It gets the startup process guide and walks you through problem clarification
3. It calls `write_protocol_document` to capture what you discuss

**Returning to a project:**
1. Agent calls `run_clarity`, gets a staleness report with the recommended process guide inlined
2. It follows the guide, updating documents as it goes

**During implementation:**
- Calls `check_decision` before significant architectural choices
- Calls `record_decision` after making a choice
- Calls `record_failure` when spotting a risk

## Options

| Flag | Default | Description |
|---|---|---|
| `--project-dir DIR` | `CLARITY_PROJECT_DIR` env var, then cwd | Project directory to operate on |
| `--transport TYPE` | `stdio` | Transport: `stdio`, `sse`, or `streamable-http` |
| `--port PORT` | `8421` | Port for SSE/HTTP transport |