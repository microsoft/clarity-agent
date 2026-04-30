"""
Packet generator for human review flows.

Assembles readable documents from clarity protocol content for distribution
to human reviewers. Each "packet" is a subset of the protocol — problem
statement, stakeholders, failures, etc. — rendered into a legible format.

Architecture:

- **Content sources** (:class:`ContentSource` subclasses) know how to collect
  content from different kinds of protocol structures (single files,
  directories of files, mailboxes, etc.).
- **Format renderers** turn the collected content into a final document
  (Markdown, HTML, PDF, etc.).
- Both are registered by name and looked up at generation time, making the
  system extensible in both dimensions.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from clarity_agent.protocol.packet_status import is_template

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class PacketContent:
    """Content collected from one source, ready for rendering.

    Attributes:
        title: Section title (e.g. "Failure Modes").
        intro: Introductory / overview content, rendered first, as markdown. ``None`` if absent.
        sections: Individual sub-items as title → content, with the content as markdown.
            ``None`` if no additional sections are required beyond the index.
    """
    title: str
    intro: str | None = None
    sections: dict[str, str] | None = None


@dataclass
class PacketPart:
    """A logical group of related sections in the packet.

    Parts establish a canonical document order (e.g. Intro → Solution →
    Failure Modes → Decisions) and produce visual separators in the
    rendered output.

    Attributes:
        title: Part title (e.g. "Intro", "Solution").
        sections: The collected content sources belonging to this part.
    """
    title: str
    sections: list[PacketContent]


@dataclass
class Packet:
    """Everything a renderer needs to produce a packet document.

    Attributes:
        title: Document title, taken from the project summary heading
            (falls back to ``"Review Packet"`` when no summary exists).
        summary: Short project summary text (the body of ``summary.md``,
            without the heading). ``None`` if unavailable.
        parts: Canonical-ordered content parts to render.
    """
    title: str
    summary: str | None
    parts: list[PacketPart]


@dataclass
class PacketView:
    """A named preset for packet generation.

    Defines which sources to include and how to group them into parts,
    giving different audiences a document tailored to their concerns.

    Attributes:
        id: Machine-readable identifier (e.g. ``"reviewer"``, ``"engineer"``).
        title: Human-readable name (e.g. ``"Reviewer"``).
        description: One-line description of what this view emphasizes.
        parts: Ordered list of ``(part_title, [source_ids])`` tuples,
            same structure as :data:`_CANONICAL_PARTS`.
    """
    id: str
    title: str
    description: str
    parts: list[tuple[str, list[str]]]


class PacketError(Exception):
    """Raised for errors during packet generation."""


# ---------------------------------------------------------------------------
# Content source hierarchy
# ---------------------------------------------------------------------------

class ContentSource(ABC):
    """Abstract source of content for a packet section.

    Subclasses implement :meth:`collect` to read content from wherever it
    lives (a single file, a directory, a mailbox, etc.) and return a
    :class:`PacketContent` describing what was found.
    """

    def __init__(self, title: str) -> None:
        self.title = title

    @abstractmethod
    def collect(self, protocol_dir: Path) -> PacketContent | None:
        """Collect content from this source.

        Returns a :class:`PacketContent` with the collected material, or
        ``None`` if nothing is available (e.g. all files are templates).
        """
        ...


class SingleFileSource(ContentSource):
    """Reads a single protocol document.

    Returns :class:`PacketContent` with the file content in *index* and
    *sections* left as ``None``.
    """

    def __init__(self, title: str, path: str) -> None:
        super().__init__(title)
        self.path = path  # relative to protocol_dir

    def collect(self, protocol_dir: Path) -> PacketContent | None:
        file_path: Path = protocol_dir / self.path
        if not file_path.exists() or is_template(file_path):
            return None
        try:
            content: str = file_path.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError:
            content = file_path.read_text().strip()
        if not content:
            return None
        return PacketContent(title=self.title, intro=content)


# Regex to extract the first markdown heading from a file.
_HEADING_RE: re.Pattern[str] = re.compile(r"^#+\s+(.+)$", re.MULTILINE)


class DirectorySource(ContentSource):
    """Reads an index file plus individual files from a protocol directory.

    Returns :class:`PacketContent` with the index in *intro* (if
    non-template) and each individual file in *sections*, keyed by the
    first markdown heading found in the file (falling back to the stem).
    """

    def __init__(self, title: str, directory: str, index_file: str, *, include_index: bool = True) -> None:
        super().__init__(title)
        self.directory = directory    # relative to protocol_dir
        self.index_file = index_file  # relative to self.directory
        self.include_index = include_index

    def collect(self, protocol_dir: Path) -> PacketContent | None:
        dir_path: Path = protocol_dir / self.directory
        if not dir_path.is_dir():
            return None

        # Read the index file (if requested).
        index_path: Path = dir_path / self.index_file
        intro_content: str | None = None
        if self.include_index and index_path.exists() and not is_template(index_path):
            try:
                text: str = index_path.read_text(encoding="utf-8").strip()
            except UnicodeDecodeError:
                text = index_path.read_text().strip()
            if text:
                intro_content = text

        # Read individual files (everything except the index).
        sections: dict[str, str] = {}
        for f in sorted(dir_path.iterdir()):
            if f.name == self.index_file or f.suffix != ".md" or not f.is_file():
                continue
            if is_template(f):
                continue
            try:
                text = f.read_text(encoding="utf-8").strip()
            except UnicodeDecodeError:
                text = f.read_text().strip()
            if not text:
                continue
            m: re.Match[str] | None = _HEADING_RE.search(text)
            section_title: str = m.group(1) if m else f.stem
            sections[section_title] = text

        if intro_content is None and not sections:
            return None

        return PacketContent(
            title=self.title,
            intro=intro_content,
            sections=sections if sections else None,
        )


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

_SOURCES: dict[str, ContentSource] = {}


def register_source(name: str, source: ContentSource) -> None:
    """Register a named content source for use in :func:`generate_packet`."""
    _SOURCES[name] = source


def get_source(name: str) -> ContentSource:
    """Look up a registered content source by name.

    Raises :class:`PacketError` if the name is not registered.
    """
    if name not in _SOURCES:
        raise PacketError(
            f"Unknown content source '{name}'. "
            f"Available: {', '.join(sorted(_SOURCES))}"
        )
    return _SOURCES[name]


def list_sources() -> list[str]:
    """Return the names of all registered content sources."""
    return sorted(_SOURCES)


def list_sources_with_titles() -> list[dict[str, str]]:
    """Return registered content sources as ``[{id, title}]`` pairs."""
    return [
        {"id": name, "title": _SOURCES[name].title}
        for name in sorted(_SOURCES)
    ]


def list_parts() -> list[dict[str, object]]:
    """Return canonical part structure as ``[{title, source_ids}]``.

    Each entry maps a part title to the ordered list of source IDs
    belonging to that part.  Used by the frontend to render
    hierarchical section selection.
    """
    return [
        {"title": title, "source_ids": source_ids}
        for title, source_ids in _CANONICAL_PARTS
    ]


# ---------------------------------------------------------------------------
# View registry
# ---------------------------------------------------------------------------

_VIEWS: dict[str, PacketView] = {}


def register_view(view: PacketView) -> None:
    """Register a named packet view."""
    _VIEWS[view.id] = view


def get_view(view_id: str) -> PacketView:
    """Look up a registered packet view by ID.

    Raises :class:`PacketError` if the ID is not registered.
    """
    if view_id not in _VIEWS:
        raise PacketError(
            f"Unknown view '{view_id}'. Available: {', '.join(sorted(_VIEWS))}"
        )
    return _VIEWS[view_id]


def list_views_with_parts() -> list[dict[str, object]]:
    """Return all views with their full parts structure.

    Each entry includes ``id``, ``title``, ``description``, and ``parts``
    (as ``[{title, source_ids}]``).  Used by the frontend to render the
    view selector and dynamically adjust the section grouping.
    """
    return [
        {
            "id": v.id,
            "title": v.title,
            "description": v.description,
            "parts": [
                {"title": title, "source_ids": source_ids}
                for title, source_ids in v.parts
            ],
        }
        for v in _VIEWS.values()
    ]


class _ThreatModelVisualSource(ContentSource):
    """Reads the LLM-generated threat model visualization.

    Looks for common filenames the LLM may use. Returns the first found.
    """

    _CANDIDATE_FILES: list[str] = [
        "threat-model.md",
        "THREAT_MODEL.md",
        "threat_model.md",
    ]

    def collect(self, protocol_dir: Path) -> PacketContent | None:
        for filename in self._CANDIDATE_FILES:
            path: Path = protocol_dir / filename
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8").strip()
                except UnicodeDecodeError:
                    content = path.read_text().strip()
                if content:
                    return PacketContent(title=self.title, intro=content)
        return None


# Regex matching fenced Mermaid code blocks in markdown.
_MERMAID_BLOCK_RE: re.Pattern[str] = re.compile(
    r"```mermaid\s*\n(.*?)```",
    re.DOTALL,
)


class _ThreatDiagramSource(ContentSource):
    """Extracts Mermaid diagrams from protocol markdown files.

    The LLM writes the diagram directly — it produces better diagrams
    than any code-generated approach. This source simply extracts
    fenced ``mermaid`` code blocks from the files where diagrams live.

    No JSON parsing, no type classification, no flow normalization.
    If the project doesn't have a fenced Mermaid block yet, re-run
    the architecture-design process (which now writes one inline).
    """

    # Files to scan for Mermaid blocks, in priority order.
    _SOURCES: list[str] = [
        "solution/architecture.md",
        "threat-model.md",
        "threat_model.md",
        "THREAT_MODEL.md",
    ]

    def collect(self, protocol_dir: Path) -> PacketContent | None:
        for rel_path in self._SOURCES:
            path: Path = protocol_dir / rel_path
            if not path.exists() or is_template(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text()
            blocks: list[str] = []
            for match in _MERMAID_BLOCK_RE.finditer(text):
                mermaid_code = match.group(1).strip()
                if mermaid_code:
                    blocks.append(f"```mermaid\n{mermaid_code}\n```")
            if blocks:
                return PacketContent(
                    title=self.title,
                    intro="\n\n".join(blocks),
                )
        return None


# Built-in sources.
register_source("problem", SingleFileSource("Problem Statement", "goal/problem.md"))
register_source("stakeholders", SingleFileSource("Stakeholders", "goal/stakeholders.md"))
register_source("requirements", SingleFileSource("Requirements", "goal/requirements.md"))
register_source("openquestions", SingleFileSource("Open Questions", "goal/open-questions.md"))
register_source("resolvedquestions", SingleFileSource("Resolved Questions", "goal/resolved-questions.md"))
register_source("solution", SingleFileSource("Solution", "solution/solution.md"))
register_source("solution_summary", SingleFileSource("Solution Summary", "solution/solution-summary.md"))
register_source("architecture", SingleFileSource("Architecture", "solution/architecture.md"))
register_source("threat_model", _ThreatModelVisualSource("Threat Model Analysis"))
register_source("threat_diagram", _ThreatDiagramSource("Threat Model Diagram"))
register_source("failures_index", SingleFileSource("Failures Overview", "failures/failures.md"))
register_source("failures_detail", DirectorySource("Failure Analysis", "failures", "failures.md", include_index=False))
register_source("decisions", DirectorySource("Decisions", "decisions", "decisions.md"))
register_source("messaging", SingleFileSource("Messaging and Audiences", "messaging.md"))
register_source("notes", SingleFileSource("Notes", "notes.md"))
register_source("observations", SingleFileSource("Observations", "observations.md"))


# ---------------------------------------------------------------------------
# Canonical part ordering
# ---------------------------------------------------------------------------

_CANONICAL_PARTS: list[tuple[str, list[str]]] = [
    ("The Problem and the Solution", ["problem", "openquestions", "solution_summary", "failures_index"]),
    ("Detailed Design", ["solution", "architecture", "notes"]),
    ("Failure Analysis", ["failures_detail", "threat_diagram", "threat_model"]),
    ("Messaging and Audiences", ["messaging"]),
    ("Appendix 1: Product Details", ["stakeholders", "requirements"]),
    ("Appendix 2: Decisions", ["resolvedquestions", "decisions"]),
    ("Appendix 3: Additional Notes", ["observations"]),
]


# Built-in views.
register_view(PacketView(
    id="complete",
    title="Complete",
    description="Full packet with all sections in canonical order.",
    parts=list(_CANONICAL_PARTS),
))
register_view(PacketView(
    id="short",
    title="The Short Version",
    description="Short packet to get people up to speed quickly",
    parts=[
        ("The Problem", ["problem", "openquestions"]),
        ("The Approach", ["solution_summary"]),
        ("What Could Go Wrong", ["failures_index"]),
        ("The Story", ["messaging"]),
    ]
))
register_view(PacketView(
    id="product_manager",
    title="Product-Focused",
    description="Product-focused view highlighting the what and the why.",
    parts=[
        ("Problem", ["problem", "openquestions"]),
        ("Product Details", ["requirements", "stakeholders"]),
        ("Solution Overview", ["solution_summary", "failures_index"]),
        ("Messaging and Audiences", ["messaging"]),
    ],
))
register_view(PacketView(
    id="engineer",
    title="Engineering-Focused",
    description="Architecture and detailed design up front, with failure analysis.",
    parts=[
        ("Problem Context", ["problem", "requirements", "solution_summary"]),
        ("Architecture and Design", ["solution", "architecture"]),
        ("Failure Analysis", ["failures_index", "failures_detail", "threat_diagram", "threat_model"]),
        ("Decisions", ["decisions", "resolvedquestions"]),
    ],
))
register_view(PacketView(
    id="reviewer",
    title="Launch Review",
    description="Failure-analysis focused review packet with design appendix.",
    parts=[
        ("Problem and Solution", ["problem", "openquestions", "solution_summary", "failures_index"]),
        ("Failure Analysis", ["failures_detail", "threat_diagram", "threat_model"]),
        ("Appendix: Detailed Design", ["solution", "architecture", "notes"]),
    ],
))
register_view(PacketView(
    id="program_manager",
    title="Project Management",
    description="Operational view highlighting tracking, decisions, and risk.",
    parts=[
        ("Problem and Solution", ["problem", "solution_summary"]),
        ("Decisions and Questions", ["decisions", "resolvedquestions", "openquestions"]),
        ("Risk Overview", ["failures_index", "threat_model"]),
    ],
))


def _assemble_parts(
    collected: dict[str, PacketContent],
    parts_def: list[tuple[str, list[str]]] | None = None,
) -> list[PacketPart]:
    """Group collected content into parts.

    Uses *parts_def* if provided, otherwise falls back to
    :data:`_CANONICAL_PARTS`.  Any sources not covered by the definition
    are placed in a trailing "Additional" part.
    """
    ordering = parts_def if parts_def is not None else _CANONICAL_PARTS
    parts: list[PacketPart] = []
    used: set[str] = set()

    for part_title, source_names in ordering:
        sections: list[PacketContent] = []
        for name in source_names:
            if name in collected:
                sections.append(collected[name])
                used.add(name)
        if sections:
            parts.append(PacketPart(title=part_title, sections=sections))

    # Remaining sources not in canonical order.
    remaining: list[PacketContent] = [
        collected[name] for name in sorted(collected)
        if name not in used
    ]
    if remaining:
        parts.append(PacketPart(title="Additional", sections=remaining))

    return parts


# ---------------------------------------------------------------------------
# Format registry
# ---------------------------------------------------------------------------

FormatRenderer = Callable[[Packet], bytes]

_FORMAT_REGISTRY: dict[str, FormatRenderer] = {}


def register_format(name: str, renderer: FormatRenderer) -> None:
    """Register a named format renderer for use in :func:`generate_packet`."""
    _FORMAT_REGISTRY[name] = renderer


def list_formats() -> list[str]:
    """Return the names of all registered format renderers."""
    return sorted(_FORMAT_REGISTRY)


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------

# Regex matching a leading ``# Title`` line.
_SUMMARY_HEADING_RE: re.Pattern[str] = re.compile(
    r"^#\s+(.+)$", re.MULTILINE,
)


def _read_summary(protocol_dir: Path) -> tuple[str, str | None]:
    """Read ``summary.md`` and extract the project title and body.

    Returns ``(title, body)``.  If ``summary.md`` is missing, a template,
    or empty, returns ``("Review Packet", None)``.
    """
    summary_path: Path = protocol_dir / "summary.md"
    if not summary_path.exists() or is_template(summary_path):
        return "Review Packet", None

    try:
        text: str = summary_path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        text = summary_path.read_text().strip()
    if not text:
        return "Review Packet", None

    m: re.Match[str] | None = _SUMMARY_HEADING_RE.search(text)
    if not m:
        return "Review Packet", text or None

    title: str = m.group(1).strip()
    body: str = text[m.end():].strip()
    return title, body if body else None


# ---------------------------------------------------------------------------
# Size estimation
# ---------------------------------------------------------------------------

def _count_words(content: PacketContent) -> int:
    """Count words in a collected content source."""
    total = 0
    if content.intro:
        total += len(content.intro.split())
    if content.sections:
        for text in content.sections.values():
            total += len(text.split())
    return total


def estimate_source_sizes(protocol_dir: Path) -> dict[str, int]:
    """Estimate word counts for each registered source.

    Returns a dict mapping source ID to word count.  Sources that are
    empty or template-only are omitted.
    """
    sizes: dict[str, int] = {}
    for name, source in _SOURCES.items():
        content = source.collect(protocol_dir)
        if content is not None:
            wc = _count_words(content)
            if wc > 0:
                sizes[name] = wc
    return sizes


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def generate_packet(
    protocol_dir: Path,
    include: list[str] | None = None,
    format: str = "markdown",
    view: str | None = None,
) -> bytes:
    """Generate a review packet from protocol content.

    The document title is taken from ``summary.md`` (falling back to
    "Review Packet"), and the summary body is rendered as a preamble
    before the table of contents.  The summary is always included when
    available, regardless of *include*.

    Args:
        protocol_dir: Path to the ``.clarity-protocol/`` directory.
        include: Source names to include (e.g. ``["problem", "failures"]``).
            If ``None``, all registered sources are tried (or all sources
            in the selected *view*).
        format: Name of the output format (default ``"markdown"``).
        view: Optional view ID. When provided, the view determines which
            sources to collect and how to group them into parts.  *include*
            further filters within the view's sources if also provided.

    Returns:
        The rendered packet as bytes (UTF-8 for text formats, binary for
        formats like docx).

    Raises:
        PacketError: If a requested source, format, or view is unknown,
            or if no content was collected (all sources were empty/template).
    """
    if format not in _FORMAT_REGISTRY:
        raise PacketError(
            f"Unknown format '{format}'. Available: {', '.join(sorted(_FORMAT_REGISTRY))}"
        )

    parts_def: list[tuple[str, list[str]]] | None = None

    if view is not None:
        v: PacketView = get_view(view)
        parts_def = v.parts
        view_sources: list[str] = [sid for _, sids in v.parts for sid in sids]
        if include is not None:
            view_set = set(view_sources)
            source_names = [s for s in include if s in view_set]
        else:
            source_names = view_sources
    else:
        source_names = include if include is not None else list_sources()

    collected: dict[str, PacketContent] = {}
    for name in source_names:
        source: ContentSource = get_source(name)  # raises PacketError if unknown
        content: PacketContent | None = source.collect(protocol_dir)
        if content is not None:
            collected[name] = content

    if not collected:
        raise PacketError("No content collected — all requested sources are empty or template.")

    title, summary = _read_summary(protocol_dir)
    parts: list[PacketPart] = _assemble_parts(collected, parts_def)
    renderer: FormatRenderer = _FORMAT_REGISTRY[format]
    return renderer(Packet(title=title, summary=summary, parts=parts))


# Auto-register built-in renderers.
from clarity_agent.packet import markdown as _markdown_module  # noqa: E402, F401

try:
    from clarity_agent.packet import docx as _docx_module  # noqa: E402, F401
except ImportError:
    pass  # python-docx / mistune not installed
