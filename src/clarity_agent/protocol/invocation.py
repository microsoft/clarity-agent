"""How to re-invoke the packet-status CLI from wherever we happen to be running.

The process guides in ``processes/*.md`` tell the agent to shell out to the
packet-status tool to read and record document state.  Those guides are static
markdown, so historically they hardcoded::

    python -m clarity_agent.protocol.packet_status . --record goal/problem.md

That command is wrong in two of the three environments Clarity runs in:

- **Frozen desktop build (PyInstaller).**  There is no ``python`` on the PATH a
  macOS GUI app inherits, and even if there were, ``clarity_agent`` is bundled
  as data inside ``sys._MEIPASS`` rather than installed into any interpreter's
  site-packages.  The agent gets ``command not found`` or
  ``No module named clarity_agent`` and silently falls back to hand-editing
  ``config.json`` — which then drifts from the hashes the tool would compute.
- **Anywhere ``python`` means Python 2 or nothing at all.**  ``python3`` is the
  only name guaranteed to exist on modern macOS and most Linux distros.

Rather than teach every guide about every environment, the guides keep the
canonical dev-mode spelling and we rewrite it at load time via
:func:`render_guide`, substituting an invocation that is correct for the
running process.  ``sys.executable`` is always the right interpreter by
construction: it is the one that imported this module.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from clarity_agent.app_paths import get_bundle_dir, is_frozen

#: The literal command spelled in ``processes/*.md``.  Guides are written
#: against the development environment; :func:`render_guide` rewrites this
#: to whatever actually works here.
GUIDE_COMMAND = "python -m clarity_agent.protocol.packet_status"


def packet_status_command() -> str:
    """Return a shell-ready command prefix that runs the packet-status CLI.

    In a frozen build this is the Clarity binary's own ``status`` subcommand,
    which needs no external interpreter and no importable ``clarity_agent``.
    Note that a PyInstaller one-file binary re-extracts its bundle on each
    launch, so this costs a second or so per call — acceptable for a command
    the agent runs a handful of times per session, and the only invocation
    that is guaranteed to work.

    In development (and under the MCP server, and in tests) it is the current
    interpreter with ``-m``.  That interpreter can import ``clarity_agent`` by
    definition, since it imported this module.
    """
    exe = shlex.quote(sys.executable)
    if is_frozen():
        return f"{exe} status"
    return f"{exe} -m clarity_agent.protocol.packet_status"


def python_path_entry(agent_dir: Path | None = None) -> str:
    """Return the directory to put on ``PYTHONPATH`` so ``clarity_agent`` imports.

    Used when spawning child processes that may run bare ``python -m
    clarity_agent...`` commands of their own.  The bundle layout differs from
    the source layout: ``clarity-server.spec`` maps ``src/clarity_agent`` to
    ``clarity_agent`` at the bundle root, so in a frozen build the importable
    directory is ``sys._MEIPASS`` itself, *not* ``sys._MEIPASS/src`` — which
    never exists.

    *agent_dir* overrides the installation root for the source layout (an
    embedded or explicitly configured install); it is ignored when frozen,
    where the bundle is the only place the package exists.
    """
    if is_frozen():
        return str(get_bundle_dir())
    return str((agent_dir or get_bundle_dir()) / "src")


def render_guide(text: str) -> str:
    """Rewrite packet-status invocations in a process guide for this environment.

    Returns *text* unchanged when the canonical spelling already works, so
    guides read naturally in the common development case.
    """
    command = packet_status_command()
    if command == GUIDE_COMMAND:
        return text
    return text.replace(GUIDE_COMMAND, command)
