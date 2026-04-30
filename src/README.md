# clarity_agent

Python package used by the clarity agent's processes. These modules are the programmatic backbone — called by process guides (like `clarity-agent.md`) and by the clarity CLI (`clarity.py`).

## Installation

For development (enables imports and type checking):

```bash
pip install -e .
```

Or just run the CLI directly — it handles the import path automatically.

## init_protocol

Initializes a `.clarity-protocol/` directory for a project. Creates the directory structure, `config.json`, template files, and optionally copies the `AGENTS.md` adapter template.

```bash
# Initialize in the current directory
python src/clarity_agent/protocol/initialize.py .

# Initialize and copy AGENTS.md template
python src/clarity_agent/protocol/initialize.py .

# Initialize a specific project directory
python src/clarity_agent/protocol/initialize.py /path/to/project
```

Safe to run on partially-initialized projects — skips files that already exist.

## packet_status

Tracks document dependencies using content hashes (SHA-256) and reports which documents need updating. Like a build system, it records the hash of each dependency at the time a document was last accepted, then detects when dependencies have changed.

```text
problem.md → stakeholders.md → requirements.md → solution.md → failures/failures.md
                                                             → architecture.md
                                                               ↕ (cycle with failures)
```

### How It Works

1. **Record baseline**: After a process updates documents, record their content hashes with `--record`
2. **Check status**: Compare current content hashes against recorded dependency hashes
3. **Recommend next step**: Walk the dependency graph and identify the first document needing attention (`--next`)

Content hashes are stored in `config.json` under `documentState`. This approach is immune to mtime artifacts from git operations, editors, or file copies — only actual content changes trigger a stale status.

### Usage

```bash
# Recommended next action (used by clarity-agent)
python src/clarity_agent/protocol/packet_status.py /path/to/project --next

# Human-readable report
python src/clarity_agent/protocol/packet_status.py /path/to/project

# Verbose (show which dependencies changed)
python src/clarity_agent/protocol/packet_status.py /path/to/project -v

# JSON output (for scripting)
python src/clarity_agent/protocol/packet_status.py /path/to/project --json

# Agent-friendly markdown (for AI system prompts)
python src/clarity_agent/protocol/packet_status.py /path/to/project --agent

# Record baseline hashes for all documents
python src/clarity_agent/protocol/packet_status.py /path/to/project --record

# Record specific documents only
python src/clarity_agent/protocol/packet_status.py /path/to/project --record goal/problem.md goal/stakeholders.md
```

### Custom Dependencies

Projects can override the default dependency graph in `config.json`:

```json
{
  "dependencies": {
    "goal/requirements.md": ["goal/problem.md", "goal/stakeholders.md", "some/custom-doc.md"]
  }
}
```

Overrides apply per-document — documents not mentioned keep their defaults.
