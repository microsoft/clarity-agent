"""Entry point for the Clarity Agent MCP server.

Usage::

    python -m clarity_agent.mcp [--project-dir DIR] [--transport stdio|sse]
"""

from __future__ import annotations

import argparse
import os


def main() -> None:
    """Parse arguments and run the MCP server."""
    parser = argparse.ArgumentParser(
        prog="python -m clarity_agent.mcp",
        description="Clarity Agent MCP server",
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        help=(
            "Project directory to operate on. "
            "Defaults to CLARITY_PROJECT_DIR env var, then cwd."
        ),
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for SSE/HTTP transport (default: 8421)",
    )

    args = parser.parse_args()

    # Set project dir in environment so all tools can resolve it
    if args.project_dir:
        os.environ["CLARITY_PROJECT_DIR"] = args.project_dir

    from clarity_agent.mcp.server import mcp

    if args.transport != "stdio":
        from clarity_agent.mcp.server import DEFAULT_SSE_PORT
        mcp.settings.host = "127.0.0.1"
        mcp.settings.port = args.port or DEFAULT_SSE_PORT

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
