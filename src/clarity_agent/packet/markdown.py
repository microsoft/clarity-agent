"""Markdown format renderer for review packets.

Produces a clean, human-readable Markdown document from collected
:class:`~clarity_agent.packet.PacketContent` sections. Legibility is the
foremost concern — these documents are sent to busy humans who need to
read and think about the material.
"""

from __future__ import annotations

from datetime import datetime, timezone

from clarity_agent.packet import Packet, register_format


def render_markdown(packet: Packet) -> bytes:
    """Render collected packet content as a Markdown document.

    Layout:
    - ``# <project title>`` heading (from summary, or "Review Packet")
    - Summary text (if available)
    - Table of contents grouped by part
    - For each :class:`PacketPart`, separated by ``---``:
      - Each :class:`PacketContent` as a ``##`` section, with directory
        sub-items as ``###`` subsections
    - Footer with generation timestamp
    """
    out: list[str] = []

    # Title.
    out.append(f"# {packet.title}\n\n")

    # Summary preamble.
    if packet.summary:
        out.append(f"{packet.summary}\n\n")

    # Table of contents, grouped by part.
    out.append("## Contents\n\n")
    for part in packet.parts:
        out.append(f"**{part.title}**\n")
        for section in part.sections:
            anchor: str = section.title.lower().replace(" ", "-")
            out.append(f"- [{section.title}](#{anchor})\n")
        out.append("\n")

    # Parts with separators.
    for part in packet.parts:
        out.append("---\n\n")
        for section in part.sections:
            out.append(f"## {section.title}\n\n")

            if section.intro is not None:
                out.append(section.intro)
                out.append("\n\n")

            if section.sections:
                for title, content in section.sections.items():
                    out.append(f"### {title}\n\n")
                    out.append(content)
                    out.append("\n\n")

    # Footer.
    now: str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out.append(f"---\n\n*Generated {now}*\n")

    return "".join(out).encode("utf-8")


# Register on import.
register_format("markdown", render_markdown)
