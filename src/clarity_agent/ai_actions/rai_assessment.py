"""Tools and context loading for standalone Responsible AI assessments."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from clarity_agent.llm.types import ToolCallback, ToolUseBlock

MAX_PROJECT_DOCUMENT_BYTES = 1_000_000
DEFAULT_ASSESSMENT_PATH = "rai-assessment.md"

READ_PROJECT_PLAN_TOOL: dict[str, Any] = {
    "name": "read_project_plan",
    "description": (
        "Read the user-provided Markdown project plan from the assessed project. "
        "Call this before beginning a Responsible AI assessment."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the project plan, relative to the project root.",
            },
        },
        "required": ["path"],
    },
}

WRITE_RAI_ASSESSMENT_TOOL: dict[str, Any] = {
    "name": "write_rai_assessment",
    "description": (
        "Write or replace the current Responsible AI assessment as Markdown. "
        "Use this whenever the assessment changes so interrupted sessions retain progress."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Complete Markdown content for the assessment.",
            },
            "path": {
                "type": "string",
                "description": (
                    "Output path relative to the project root. "
                    f"Defaults to {DEFAULT_ASSESSMENT_PATH}."
                ),
            },
        },
        "required": ["content"],
    },
}

_GUIDANCE_FILES: tuple[tuple[str, str], ...] = (
    ("Responsible AI background", "rai-context/rai-background.md"),
    ("Sensitive Use guidance", "rai-context/sensitive-use-cases.md"),
    ("Responsible AI thinker", "thinkers/responsible-ai-thinker.md"),
)


def load_rai_guidance(clarity_agent_dir: Path) -> str:
    """Load the bundled guidance required by the RAI assessment process."""
    sections: list[str] = []
    for title, relative_path in _GUIDANCE_FILES:
        path = clarity_agent_dir / relative_path
        if path.is_file():
            content = path.read_text(encoding="utf-8")
        else:
            content = f"Required source unavailable: {relative_path}"
        sections.append(f"## {title}\n\n{content.strip()}")
    return "\n\n".join(sections)


def _resolve_markdown_path(project_dir: Path, raw_path: str) -> Path:
    """Resolve a Markdown path while confining it to the project root."""
    project_root = project_dir.resolve()
    requested = Path(raw_path)
    path = (requested if requested.is_absolute() else project_root / requested).resolve()
    if not path.is_relative_to(project_root):
        raise ValueError("Path must stay within the assessed project")
    if path.suffix.lower() != ".md":
        raise ValueError("Path must identify a Markdown document")
    return path


def read_project_plan(project_dir: Path, plan_path: str) -> tuple[Path, str]:
    """Read a user-selected Markdown project plan from the project root."""
    path = _resolve_markdown_path(project_dir, plan_path)
    if not path.is_file():
        raise FileNotFoundError(f"Project plan not found: {plan_path}")
    if path.stat().st_size > MAX_PROJECT_DOCUMENT_BYTES:
        raise ValueError("Project plan exceeds the 1 MB size limit")
    return path, path.read_text(encoding="utf-8")


def write_rai_assessment(
    project_dir: Path,
    content: str,
    output_path: str = DEFAULT_ASSESSMENT_PATH,
) -> Path:
    """Write the complete RAI assessment within the project root."""
    if not content.strip():
        raise ValueError("Assessment content cannot be empty")
    path = _resolve_markdown_path(project_dir, output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return path


def create_rai_assessment_handler(
    project_dir: Path,
    *,
    on_tool_use: ToolCallback | None = None,
) -> Callable[[ToolUseBlock], str]:
    """Create the handler for standalone RAI assessment tools."""

    def handle(tool_call: ToolUseBlock) -> str:
        try:
            if tool_call.name == "read_project_plan":
                path, content = read_project_plan(project_dir, tool_call.input["path"])
                if on_tool_use:
                    on_tool_use("read_project_plan", str(path))
                return content
            if tool_call.name == "write_rai_assessment":
                path = write_rai_assessment(
                    project_dir,
                    tool_call.input["content"],
                    tool_call.input.get("path", DEFAULT_ASSESSMENT_PATH),
                )
                if on_tool_use:
                    on_tool_use("write_rai_assessment", str(path))
                return f"Assessment written to {path}"
        except (FileNotFoundError, KeyError, OSError, TypeError, ValueError) as exc:
            return f"Error: {exc}"
        return f"Unknown tool: {tool_call.name}"

    return handle


def create_rai_assessment_tools() -> list[dict[str, Any]]:
    """Return the tool schemas used by the RAI assessment process."""
    return [READ_PROJECT_PLAN_TOOL, WRITE_RAI_ASSESSMENT_TOOL]
