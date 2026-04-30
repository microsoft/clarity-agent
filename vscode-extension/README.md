# Clarity Agent

Think clearly about what you're building, why, and what could go wrong — right inside VS Code.

Clarity Agent guides you through structured problem clarification, solution design, and failure analysis using LLMs. It lives in the sidebar, like any other VS Code panel.

## Getting Started

1. **Install the `.vsix`**
   ```
   code --install-extension clarity-agent-1.0.0.vsix
   ```
2. **Click the Clarity icon** in the Activity Bar (left sidebar).
3. **Click "Start Clarity"** — the extension will prompt you to install Python dependencies if needed.
4. **Follow the setup wizard** to configure your LLM provider (Azure OpenAI, OpenAI, or Anthropic).

That's it. Start describing what you're building and Clarity will walk you through it.

## Requirements

- **Python 3.10+** on your PATH
- An API key for at least one LLM provider (the setup wizard will guide you)

## Commands

| Command | What it does |
|---|---|
| **Clarity: Open** | Start Clarity for the current workspace (or pick a folder) |
| **Clarity: Open Project...** | Choose a specific project directory |
| **Clarity: Doctor** | Run diagnostics if something isn't working |
| **Clarity: Restart Backend** | Restart the backend process |

## Settings

| Setting | Default | Description |
|---|---|---|
| `clarity.pythonPath` | auto | Path to Python. Leave empty to auto-detect. |
| `clarity.port` | auto | Backend port. `0` = let the OS pick one. |