"""Word document format renderer for review packets.

Produces a visually clean ``.docx`` file from collected packet content.
This module is a thin orchestrator — it walks the part/section hierarchy
and delegates all element-level rendering to :class:`DocumentStyle`.

To change how the document looks, edit ``docx_style.py`` instead.
"""

from __future__ import annotations

import io
import re

from docx import Document

from clarity_agent.packet import Packet, register_format
from clarity_agent.packet.docx_style import DEFAULT_STYLE, DocumentStyle

# Regex matching a leading markdown heading line.
_LEADING_HEADING_RE: re.Pattern[str] = re.compile(
    r"^#+\s+.+\n*", re.MULTILINE,
)


def _strip_leading_heading(text: str) -> str:
    """Remove the first markdown heading from *text*.

    The raw content in ``PacketContent.intro`` and ``.sections`` values
    typically starts with a heading (e.g. ``# Problem``) that duplicates
    the section title already emitted by the orchestrator.
    """
    m: re.Match[str] | None = _LEADING_HEADING_RE.match(text)
    if m:
        return text[m.end():].lstrip("\n")
    return text


def render_docx(
    packet: Packet,
    style: DocumentStyle = DEFAULT_STYLE,
) -> bytes:
    """Render collected packet content as a Word document.

    Args:
        packet: The :class:`Packet` containing title, summary, and parts.
        style: The :class:`DocumentStyle` controlling appearance and
            element rendering. Defaults to :data:`DEFAULT_STYLE`.

    Returns:
        The ``.docx`` file contents as bytes.
    """
    doc = Document()
    style.setup_page(doc)
    style.add_title(doc, packet.title)

    if packet.summary:
        style.render_markdown(doc, packet.summary, 2)

    for i, part in enumerate(packet.parts):
        if i > 0:
            style.add_separator(doc)
        style.add_part_title(doc, part.title)

        for section in part.sections:
            style.add_section_heading(doc, section.title)

            if section.intro:
                style.render_markdown(
                    doc, _strip_leading_heading(section.intro), 2,
                )

            if section.sections:
                for title, content in section.sections.items():
                    style.add_subsection_heading(doc, title)
                    style.render_markdown(
                        doc, _strip_leading_heading(content), 3,
                    )

    style.add_footer(doc)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_renderer(
    style: DocumentStyle = DEFAULT_STYLE,
) -> callable:
    """Create a format renderer closure that captures the style."""
    def render(packet: Packet) -> bytes:
        return render_docx(packet, style)
    return render


# Register on import.
register_format("docx", _make_renderer())
