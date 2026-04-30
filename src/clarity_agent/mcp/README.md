# Clarity Agent, Python MCP Server

This MCP server gives coding agents access to the clarity-agent process: problem clarification, failure brainstorming, decision recording, and review packet generation. It works with any MCP-capable tool (Claude Code, GitHub Copilot CLI, Cursor, Roo).

## Why

Coding agents write code but don't stop to ask whether the right thing is being built or what could go wrong. This server adds that capability. When connected, the agent can:

- Check which protocol documents are stale and what process to run next
- Read process guides for problem clarification, solution design, failure analysis
- Record decisions, failure modes, and suggestions as structured documents
- Generate review packets for stakeholders

The agent calls these tools during normal conversation. You get structured thinking without switching tools.

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

Create or go to your project directory:

```bash
mkdir /path/to/[YOUR-PROJECT]
cd /path/to/[YOUR-PROJECT]
```

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

Replace `/path/to/clarity-agent` with the absolute path to your clarity-agent clone. On Windows, use backslashes or forward slashes (both work in VS Code).

### 5. Launch your agent

**Claude Code:**

```bash
claude
```

Claude Code reads `.mcp.json` on startup. Ask it to "run clarity" to get started.

**GitHub Copilot CLI:**

```bash
gh copilot --mcp-config .mcp.json
```

**Cursor / VS Code with Roo:**

Add the same config to `.roo/mcp.json` or Cursor's MCP settings. The command and args are identical.

> **Note:** An npm wrapper (`npx @clarity-agent/mcp`) also exists in [`mcp-server/`](../../mcp-server/README.md) for MCP clients that expect npx. It will not work until the Python package is published to PyPI. Use the Python server directly until then.

## How It Works

The server uses two directories:

- **project-dir**: your project, where `.clarity-protocol/` lives
- **agent-dir**: the installed clarity-agent package, where process guides and thinker guides live (resolved automatically)

When the agent calls `run_clarity()`, the server checks the project directory for `.clarity-protocol/`. If none exists, it returns the startup guide. If one exists, it checks document staleness and recommends the next process.

All read/write operations are scoped to the project directory with path traversal protection.

## Available Tools

| Tool | Purpose |
|---|---|
| `run_clarity` | Assess project state, recommend next step |
| `init_protocol` | Create `.clarity-protocol/` directory |
| `read_protocol_document` | Read a protocol document |
| `write_protocol_document` | Write or update a protocol document |
| `list_protocol_documents` | List all protocol files |
| `get_packet_status` | Check document staleness |
| `record_packet_status` | Record content baselines after writing documents |
| `get_next_action` | Get recommended next process |
| `record_failure` | Record a failure mode |
| `record_suggestion` | Record a document suggestion |
| `record_decision` | Record a structured decision |
| `list_processes` | List available process guides |
| `read_process_guide` | Read a process guide |
| `list_thinkers` | List failure brainstorming thinkers |
| `read_thinker_guide` | Read a thinker's methodology |
| `read_behaviors` | Read AGENTS.md behavioral guidelines |
| `generate_packet` | Generate a review packet |
| `get_mailbox_status` | Check async operation mailboxes |
| `check_failure_state` | Check failure analysis progress |

## Recommended Usage

Start every session by asking the agent to call `run_clarity`. It returns a status assessment and tells the agent which process guide to follow. The conversation flows from there.

**New project:**
1. Agent calls `run_clarity`, sees no protocol
2. It gets the startup process guide and walks you through problem clarification
3. It calls `init_protocol`, then `write_protocol_document` to capture what you discuss

**Returning to a project:**
1. Agent calls `run_clarity`, gets a staleness report
2. It identifies stale documents and the right process to update them
3. You continue where you left off

**During implementation:**
- Call `record_decision` for meaningful technical choices (library selection, architecture tradeoffs). This creates a durable record.
- Call `record_failure` when you spot a risk worth tracking.
- Call `generate_packet` before a design review or stakeholder check-in.

**Failure brainstorming:**
- `list_thinkers` shows available specialist perspectives (security, human factors, adversarial).
- `read_thinker_guide` loads a thinker's methodology. Use `record_failure` for each failure mode found.
- `check_failure_state` shows where you are in the brainstorm/analyze/manage pipeline.

The process guides produce natural conversation, not form-filling. The agent moves quickly through obvious steps and slows down for genuine ambiguity.

## Options

| Flag | Default | Description |
|---|---|---|
| `--project-dir DIR` | `CLARITY_PROJECT_DIR` env var, then cwd | Project directory to operate on |
| `--transport TYPE` | `stdio` | Transport: `stdio`, `sse`, or `streamable-http` |
| `--port PORT` | `8421` | Port for SSE/HTTP transport |

## Demo Session

A real session from Claude Code on an empty project directory. The agent invented a demo project and completed problem clarification in about 90 seconds.

```
~/Documents/Repos/tests/testing-april-17

❯ run clarity on this project

  Called clarity-agent                        # Tool: run_clarity()
                                              # Returns: no protocol found + startup guide

● This looks like a fresh project, no clarity protocol yet. What are you working on here?

❯ you can decide what im working on!

● Two options:
  1. Demo project, I invent a toy problem and we walk the clarity flow.
  2. Something real, give me a one-liner and we'll work on that.

❯ demo project

  Called clarity-agent 3 times               # Tools: init_protocol()
                                              #        read_process_guide("problem-clarification")
                                              #        read_process_guide("clarity-agent")

● Protocol initialized. Running problem clarification for a CLI tool
  that summarizes your recent git activity for standups.

  Called clarity-agent 6 times               # Tools: write_protocol_document("summary.md", ...)
                                              #        write_protocol_document("goal/problem.md", ...)
                                              #        write_protocol_document("goal/stakeholders.md", ...)
                                              #        write_protocol_document("goal/requirements.md", ...)
                                              #        write_protocol_document("goal/open-questions.md", ...)
                                              #        get_packet_status()

● All goal documents are current. Here's where we are:

  Created in .clarity-protocol/:
  - goal/problem.md, developers forget what they worked on, give vague standups
  - goal/stakeholders.md, primary user (developer), indirect (standup audience)
  - goal/requirements.md, scan local repos, filter by author/time, output bullets in <5s
  - goal/open-questions.md, how to summarize commits (heuristics vs. LLM)
  - summary.md, the elevator pitch

  Next steps:
  1. solution-brainstorming, pick an approach
  2. failure-brainstorming, think through what could go wrong
  3. discovery-prototype, test the summarization approach first

  Want to continue into solution brainstorming?

✻ Total time: 1m 23s
```

The agent called `run_clarity` to assess state, read the process guides, then used `init_protocol` and `write_protocol_document` to create all the problem clarification documents. The flow was driven by the process guide instructions, not hardcoded behavior.