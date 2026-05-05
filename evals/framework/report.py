"""Generate the ``summary.md`` report at the end of an eval run.

The summary is one central human-readable file per run.  It is
organized by test **module** (e.g. ``safety/test_terminal_suicide``)
since each module runs one shared conversation that multiple test
functions assert against; grouping this way keeps the conversation
and its artifacts with the verdicts that came from it.

Structure:

- Header: timestamp, models used, top-line pass/fail counts.
- Results: one mini-table per module.  Lists each test function
  inside that module with its outcome and duration.
- Details: one section per module, with:
    - Artifact links (folder, transcript, protocol/) at the module level
    - Per-test sub-sections containing:
        - Each judge criterion and verdict + reasoning
        - Assertion error if the test failed

The report deliberately does NOT inline the full transcript or the
content passed to the judge — those can be huge, and the preserved
folder is a better place to review them.  The summary should be
skimmable.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from evals.framework.config import EvalConfig
from evals.framework.judge import JudgeRecord

_OUTCOME_ICON: dict[str, str] = {
    "passed": "\u2705",          # ✅
    "failed": "\u274C",          # ❌
    "skipped": "\u23F8",          # ⏸
    "error": "\U0001F4A5",        # 💥
    "running": "\u23F3",         # ⏳
    # Module-level "the conversation didn't actually exercise the
    # persona's goal — downstream assertions are operating on a bad
    # sample and have been aborted."  Stop-sign octagon: distinct
    # SHAPE from the other failure icons so the outcome stays
    # readable in monochrome rendering and for users with
    # red/orange color confusion (the previous 🟥 / 🟧 pairing was
    # the same square shape distinguished only by hue).
    "smoke_failed": "\U0001F6D1", # 🛑
    # Per-test "marked @advisory, assertion failed".  Light bulb:
    # signals "improvement opportunity" rather than "stop
    # everything," and shape-distinct from 🛑 / ❌ / 💥 so a
    # colorblind reader can still tell the failure flavors apart.
    # The test's pytest outcome was rewritten to "passed" so it
    # does NOT contribute to pytest's exit code; this bucket is
    # purely for the human reading summary.md.
    "advisory_failed": "\U0001F4A1", # 💡
    # Per-test "the refusal-acceptable gate fired — the agent
    # refused cleanly, which is the desired outcome for this
    # module."  Visually identical to ``passed`` (✅) because it's
    # a SUCCESS flavor — but the report uses the text label
    # "refused" to make the specific outcome clear.  Counts toward
    # the OK bucket in the top-line summary, with its own
    # sub-category so a reviewer can see which OK tests were
    # "agent helped" vs. "agent declined."
    "refused": "✅",         # ✅ (same as passed)
}

# Per-judge-criterion icons.  ``NA`` is the "doesn't apply" verdict —
# a conditional criterion whose precondition wasn't met.  Heavy minus
# (➖) reads as "no value" and renders cleanly on light AND dark
# backgrounds, unlike the hollow shapes.
_VERDICT_ICON: dict[str, str] = {
    "YES": "\u2705",  # ✅
    "NO": "\u274C",   # ❌
    "NA": "\u2796",   # ➖
}


def _verdict_icon(verdict: str) -> str:
    """Return the display icon for a judge verdict.

    Defaults to the NO icon for unknown verdicts — those almost always
    indicate a parsing failure on the judge's side, which is closer to
    a fail than a pass for review purposes.
    """
    return _VERDICT_ICON.get(verdict, _VERDICT_ICON["NO"])


# Per-test outcome label overrides — what to display in the
# "Outcome" column of the Results table.  The dict keys are the
# raw outcome bucket names (used internally and as the icon-map
# keys); the values are the user-facing labels.  Unmapped outcomes
# render as their raw name (``passed``, ``failed``, etc.).
_TEST_OUTCOME_LABEL: dict[str, str] = {
    # ``advisory_failed`` is verbose for what's essentially "this
    # test is marked advisory and didn't pass."  Drop the suffix.
    "advisory_failed": "advisory",
    # ``smoke_failed`` means "the test was deferred because the
    # module's smoke gates fired" — it's NOT a per-test failure,
    # the test never ran.  "not run" reflects that.
    "smoke_failed": "not run",
}


def _test_outcome_label(outcome: str) -> str:
    """Return the user-facing label for a test outcome.

    Most outcomes use their raw bucket name.  ``advisory_failed``
    and ``smoke_failed`` are renamed to "advisory" and "not run"
    respectively — the bucket names carry framework-internal
    semantics that don't read well in a per-test cell.
    """
    return _TEST_OUTCOME_LABEL.get(outcome, outcome)


def _gate_verdict_display(
    reserved_name: str, verdict: str,
) -> tuple[str, str]:
    """Return ``(icon, label)`` for a smoke-gate verdict.

    Special-cased for ``__refusal__`` — that gate has inverted
    semantics where YES is REFUSED (success short-circuit) and NO
    is ENGAGED (neutral fall-through, NOT a failure).  ENGAGED
    uses the ➖ icon to signal "not applicable here, moved on" —
    same iconography as N/A criteria.  REFUSED uses ✅, identical
    to a pass.  This keeps the refusal row visually distinct from
    rows where ❌ would mean "this gate broke."

    All other gates use the standard YES=✅ / NO=❌ / NA=➖
    mapping.  Default for unknown verdicts mirrors
    :func:`_verdict_icon` — fall back to the NO icon since an
    unparseable verdict is closer to a fail than a pass.
    """
    if reserved_name == "__refusal__":
        if verdict == "YES":
            return _VERDICT_ICON["YES"], "REFUSED"
        return _VERDICT_ICON["NA"], "ENGAGED"
    label = "N/A" if verdict == "NA" else verdict
    return _verdict_icon(verdict), label


# GitHub issue URL — anchored ``^`` and ``$``-equivalent so we don't
# match e.g. a URL embedded in a longer string.  Captures the issue
# number for compact ``#NNN`` rendering.  Tolerates http:// and
# https://, optional ``www.`` prefix, optional trailing slash.
_GH_ISSUE_URL_RE = re.compile(
    r"\Ahttps?://(?:www\.)?github\.com/[^/\s]+/[^/\s]+/issues/(\d+)/?\Z",
    re.IGNORECASE,
)


def _format_issue_link_short(url: str) -> str:
    """Render *url* as a compact markdown link for use in a table cell.

    GitHub issue URLs render as ``#NNN`` linking to the URL.  Other
    URLs render as a chain-link emoji 🔗 — generic enough for any
    tracker (JIRA, Linear, internal) without claiming GitHub
    semantics.  Markdown links use ``rel=`` attributes implicitly
    via GitHub's rendering, so no special escaping needed.
    """
    stripped = url.strip()
    if not stripped:
        return ""
    m = _GH_ISSUE_URL_RE.match(stripped)
    if m:
        return f"[#{m.group(1)}]({stripped})"
    return f"[\U0001F517]({stripped})"  # 🔗


def _format_issue_link_long(url: str) -> str:
    """Render *url* as a markdown link for use in the per-test details.

    Same GH-aware shortening as :func:`_format_issue_link_short`,
    but the non-GH fallback shows the full URL as link text rather
    than just an icon — there's room in the details section, and
    seeing the URL helps reviewers spot whether it's pointing at the
    expected tracker.
    """
    stripped = url.strip()
    if not stripped:
        return ""
    m = _GH_ISSUE_URL_RE.match(stripped)
    if m:
        return f"[#{m.group(1)}]({stripped})"
    return f"[{stripped}]({stripped})"


def _parse_nodeid(nodeid: str) -> dict[str, str]:
    """Parse ``evals/cases/<category>/test_<name>.py::test_<fn>`` into components."""
    if "::" in nodeid:
        file_part, test_name = nodeid.split("::", 1)
    else:
        file_part, test_name = nodeid, ""

    parts = Path(file_part).parts
    category = ""
    module = Path(file_part).stem
    try:
        cases_idx = parts.index("cases")
        if len(parts) > cases_idx + 1:
            category = parts[cases_idx + 1]
    except ValueError:
        pass

    folder_rel = f"{category}/{module}" if category else module
    return {
        "category": category,
        "module": module,
        "test_name": test_name,
        "folder_rel": folder_rel,
    }


def _anchor(nodeid: str) -> str:
    """Stable HTML-id anchor for a test nodeid."""
    return "test-" + (
        nodeid.replace("::", "--").replace("/", "-").replace(".", "-")
    )


def _module_anchor(folder_rel: str) -> str:
    """Stable HTML-id anchor for a module's Details heading.

    Format: ``module-<category>-<module-stem>``.  Used to link from
    each per-module heading in the top-of-report Results section down
    to the corresponding Details subsection — the report is long
    enough that reviewers need the jump targets to navigate.
    """
    return "module-" + folder_rel.replace("/", "-").replace(".", "-")


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _format_duration(seconds: float) -> str:
    """Format a wall-clock duration as ``45.2s`` / ``2m 45s`` / ``1h 02m 45s``."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m {secs:02d}s"


def _load_module_metadata(
    outputs_dir: Path, folder_rel: str,
) -> dict[str, Any] | None:
    """Read ``<outputs_dir>/<folder_rel>/metadata.json`` if it exists.

    Written by the runner once the user↔target conversation completes.
    Returns ``None`` for modules whose conversation hasn't reached that
    point yet (in-flight or crashed before write-out).
    """
    path = outputs_dir / folder_rel / "metadata.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# Reserved cache keys used by the framework's two smoke-gate checks.
# Kept here (rather than imported from judge.py) so a future rename
# in judge.py forces an explicit update to the report layer too —
# the report's table-of-smoke-checks shape depends on knowing exactly
# these names.  Order matters: persona-adoption runs first (during
# converse_with), smoke check runs after the conversation completes.
_SMOKE_GATE_KEYS: list[tuple[str, str]] = [
    ("__persona_adoption__", "persona-adoption check"),
    # Refusal check runs ONLY for modules marked
    # ``@refusal_acceptable``, before substantivity (a clean turn-1
    # refusal is a valid pass for these tests).  Has inverted
    # verdict semantics from the others: REFUSED (YES) is the
    # success short-circuit, ENGAGED (NO) means "fall through to
    # the next gates."  Neither outcome is a failure, so its
    # rendering is special-cased.
    ("__refusal__", "refusal check"),
    ("__substantivity__", "substantivity check"),
    ("__goal_pursued__", "goal-pursued check"),
]


def _load_smoke_gate_records(
    outputs_dir: Path, folder_rel: str,
) -> list[tuple[str, str, JudgeRecord | None]]:
    """Return ``(reserved_name, label, record_or_None)`` per smoke gate, in run order.

    Reads ``<folder_rel>/judge_records.json`` directly rather than via
    :class:`JudgeCache.lookup`, because lookup gates on fingerprint
    match and we want the records regardless — they reflect what
    actually happened, even if the transcript was later edited.

    Either record may be ``None`` independently.  Persona-adoption
    only runs on fresh conversations (the resume path skips it
    because ``converse_with`` doesn't run); smoke runs on every
    conversation (fresh or resumed).  Both ``None`` when the cache
    file is missing or malformed — caller should skip the smoke
    section entirely in that case.
    """
    cache_path = outputs_dir / folder_rel / "judge_records.json"
    tests: dict[str, list[dict[str, Any]]] = {}
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            tests = data.get("tests") or {}
        except (OSError, json.JSONDecodeError):
            tests = {}

    def _first_record(reserved_name: str) -> JudgeRecord | None:
        entries = tests.get(reserved_name) or []
        if not entries:
            return None
        entry = entries[0]
        try:
            return JudgeRecord(
                claim=entry["claim"],
                verdict=entry["verdict"],
                reasoning=entry.get("reasoning", ""),
                elapsed=float(entry.get("elapsed", 0.0)),
                cost_usd=float(entry.get("cost_usd", 0.0)),
                cached=False,
                timestamp=entry.get("timestamp"),
            )
        except (KeyError, TypeError, ValueError):
            return None

    return [
        (reserved_name, label, _first_record(reserved_name))
        for reserved_name, label in _SMOKE_GATE_KEYS
    ]


def _smoke_anchor(folder_rel: str, reserved_name: str) -> str:
    """Anchor for a smoke-gate detail subsection.

    Format: ``smoke-<category>-<module>-<reserved>``.  Distinct from
    test anchors (which use the user-facing function name) so the
    namespaces don't collide.  ``__goal_pursued__`` becomes ``smoke``,
    ``__persona_adoption__`` becomes ``persona-adoption`` for
    readable URLs.
    """
    slug = reserved_name.strip("_").replace("_", "-")
    base = folder_rel.replace("/", "-").replace(".", "-")
    return f"smoke-{base}-{slug}"


def _failing_gate_label(
    smoke_gate_records: list[tuple[str, str, JudgeRecord | None]],
) -> str | None:
    """Return the short label of the failed smoke gate, or None.

    A smoke-failed module always has exactly one failed gate (the
    runner aborts on the first failure), so we can return one label.
    Used to qualify the module heading when ``smoke_failed`` is in
    the test counts — reviewer sees "(persona-adoption gate failed)"
    without expanding the module's table.

    Strips the trailing " check" from the label so it reads
    naturally with the "gate" suffix the heading appends — the full
    label "goal-pursued check" + " gate failed" reads as "smoke check gate
    failed" which is redundant; the short form "smoke gate failed"
    is what we want.
    """
    for reserved_name, label, rec in smoke_gate_records:
        # Skip the refusal gate: its NO verdict ("ENGAGED") is a
        # neutral fall-through, not a failure.  A smoke_failed
        # outcome on a refusal-acceptable module must have come
        # from one of the OTHER gates, so the qualifier should
        # name that gate, not refusal.
        if reserved_name == "__refusal__":
            continue
        if rec is not None and rec.verdict == "NO":
            return label.removesuffix(" check")
    return None


def _blockquote_lines(text: str) -> list[str]:
    """Return *text* rendered as a markdown blockquote (``> `` prefix)."""
    return [f"> {line}" if line else ">" for line in text.splitlines()]


def _render_scenario_block(meta: dict[str, Any]) -> list[str]:
    """Render the persona/situation/goal inside a collapsible ``<details>``.

    GitHub-flavored markdown renders ``<details>`` as expandable, so
    reviewers can skim past the scenario when skimming many modules
    and expand only the ones they want to read in full.
    """
    persona = meta.get("persona") or ""
    situation = meta.get("situation") or ""
    goal = meta.get("goal") or ""
    if not (persona or situation or goal):
        return []

    block: list[str] = [
        "<details>",
        "<summary><b>Scenario</b> — persona, situation, goal the "
        "simulated user was given</summary>",
        "",
    ]
    for label, body in (
        ("Persona", persona),
        ("Situation", situation),
        ("Goal", goal),
    ):
        if not body:
            continue
        block.append(f"**{label}:**")
        block.append("")
        block.extend(_blockquote_lines(body.strip()))
        block.append("")
    block.append("</details>")
    block.append("")
    return block


def _module_aggregate(
    outcomes: list[str], *, na_count: int = 0,
) -> tuple[str, str]:
    """Aggregate a module's per-test outcomes into (icon, stats_text).

    Icon precedence (worst wins): failed > error > running > skipped > passed.
    Stats text reads like ``5/5 passed`` or ``3/5 passed, 1 failed, 1 running``.

    ``na_count`` is the number of N/A judge verdicts inside the module —
    a *criterion-level* count, distinct from the test-level outcomes.
    Surfaced as a trailing ``N N/A criteria`` bucket so reviewers see
    that some verdicts were "doesn't apply" without having to open the
    Details section to count.  N/A doesn't influence the icon: a test
    whose criteria all returned N/A is still a passing test.
    """
    counts = Counter(outcomes)
    total = len(outcomes)

    # Icon precedence: smoke_failed outranks everything test-level
    # because it means the whole module's sample is invalid; reading
    # individual pass/fail counts on top of a bad conversation is
    # misleading, so we flag the module with the 🛑 icon first.
    # ``advisory_failed`` is the lowest-severity failure-shaped
    # bucket — it ranks ABOVE passed/skipped (so a module with one
    # advisory failure doesn't show as ✅) but BELOW everything else
    # (a real failure, smoke failure, infra error, or in-flight test
    # should outrank it for the at-a-glance icon).
    if counts.get("smoke_failed"):
        icon = _OUTCOME_ICON["smoke_failed"]
    elif counts.get("failed"):
        icon = _OUTCOME_ICON["failed"]
    elif counts.get("error"):
        icon = _OUTCOME_ICON["error"]
    elif counts.get("running"):
        icon = _OUTCOME_ICON["running"]
    elif counts.get("passed") or counts.get("refused"):
        # ``passed`` and ``refused`` both map to ✅ — a module
        # whose tests are all refused looks identical to a module
        # whose tests all passed.  The text differs (stats text
        # below).  Crucially, this branch wins over ``advisory_failed``
        # so a module that mostly passed but had a few advisory
        # failures still shows ✅ — advisories don't block, and a
        # 💡 icon on a mostly-passing module misreads as "this
        # module had problems."
        icon = _OUTCOME_ICON["passed"]
    elif counts.get("advisory_failed"):
        # Only fires when there are NO clean passes — an all-
        # advisories module gets the 💡 icon to signal "this
        # whole module is in 'needs improvement' state."
        icon = _OUTCOME_ICON["advisory_failed"]
    elif counts.get("skipped"):
        icon = _OUTCOME_ICON["skipped"]
    else:
        icon = _OUTCOME_ICON["passed"]

    parts: list[str] = []
    # Smoke-failed has special framing — don't list per-test counts
    # at all, just say the smoke test failed and how many tests
    # weren't run.  The which-gate-fired detail lives in the
    # per-gate breakdown lines at the top of the report.
    if counts.get("smoke_failed"):
        not_run = counts["smoke_failed"]
        n = "test" if not_run == 1 else "tests"
        parts.append(f"smoke test failed: {not_run} {n} not run")
        return icon, ", ".join(parts)
    # Otherwise: count passes-and-refusals as the "OK" total, with
    # advisories rolled in (advisory failures don't block — same
    # treatment as the top-line OK bucket).  Sub-categories appear
    # as inline qualifiers for readability.
    ok_total = (
        counts.get("passed", 0)
        + counts.get("refused", 0)
        + counts.get("advisory_failed", 0)
    )
    if counts.get("passed") and not counts.get("refused"):
        parts.append(f"{ok_total}/{total} passed")
    elif counts.get("refused") and not counts.get("passed"):
        parts.append(f"{ok_total}/{total} refused")
    elif counts.get("passed") and counts.get("refused"):
        # Mixed: name both.
        parts.append(f"{counts['passed']}/{total} passed")
        parts.append(f"{counts['refused']}/{total} refused")
    elif counts.get("advisory_failed"):
        # Only advisories — no clean passes — call it out as the
        # primary OK count.
        parts.append(f"{ok_total}/{total} OK")
    if counts.get("advisory_failed"):
        n = counts["advisory_failed"]
        parts.append(
            f"{n} advisor{'y' if n == 1 else 'ies'}"
        )
    if counts.get("failed"):
        parts.append(f"{counts['failed']} failed")
    if counts.get("error"):
        parts.append(f"{counts['error']} errored")
    if counts.get("skipped"):
        parts.append(f"{counts['skipped']} skipped")
    if counts.get("running"):
        parts.append(f"{counts['running']} running")
    if na_count:
        parts.append(f"{na_count} N/A criteria")
    return icon, ", ".join(parts)


def _count_na_records(
    nodeids: list[str],
    judge_records: dict[str, list[JudgeRecord]],
) -> int:
    """Count how many judge records returned NA across the given nodeids."""
    return sum(
        1
        for nodeid in nodeids
        for rec in judge_records.get(nodeid, [])
        if rec.verdict == "NA"
    )


def _first_smoke_reasoning(
    nodeids: list[str],
    test_outcomes: dict[str, dict[str, Any]],
) -> str | None:
    """Return the first non-empty smoke-check reasoning across *nodeids*.

    All tests in a smoke-failed module share the same smoke reasoning
    (one conversation, one smoke verdict), so we only surface it once
    at the module level.  ``None`` when none of the given tests were
    smoke-failed — the normal case, no banner rendered.
    """
    for nodeid in nodeids:
        info = test_outcomes.get(nodeid)
        if info is None:
            continue
        reasoning = info.get("smoke_reasoning")
        if reasoning:
            return reasoning
    return None


def _failed_to_run_breakdown(
    test_outcomes: dict[str, dict[str, Any]],
    counts: dict[str, int],
) -> list[str]:
    """Sub-bullets explaining *why* tests in the failed-to-run bucket didn't run.

    Smoke-failed and infra-errored tests cluster by module (the
    fixture for the whole module raised, so every test in the
    module got skipped together), so for those causes we report
    "N modules (M tests)" — which is the more useful framing
    because a single fix at the module level un-skips all of them.

    Plain skipped tests (``pytest.skip``) don't have that module
    correlation, so they get a flat "M tests skipped" line with no
    module count.
    """
    parts: list[str] = []
    smoke_modules: set[str] = set()
    infra_modules: set[str] = set()
    for nodeid, info in test_outcomes.items():
        if nodeid == "<unknown>":
            continue
        outcome = info.get("outcome")
        folder = _parse_nodeid(nodeid)["folder_rel"]
        if outcome == "smoke_failed":
            smoke_modules.add(folder)
        elif outcome == "error":
            infra_modules.add(folder)
    if counts["smoke_failed"]:
        n_mod = len(smoke_modules)
        n_test = counts["smoke_failed"]
        parts.append(
            f"{n_mod} {'module' if n_mod == 1 else 'modules'} "
            f"({n_test} {'test' if n_test == 1 else 'tests'}) "
            f"skipped because of smoke test failures"
        )
    if counts["error"]:
        n_mod = len(infra_modules)
        n_test = counts["error"]
        parts.append(
            f"{n_mod} {'module' if n_mod == 1 else 'modules'} "
            f"({n_test} {'test' if n_test == 1 else 'tests'}) "
            f"skipped because of infrastructure errors"
        )
    if counts["skipped"]:
        n_test = counts["skipped"]
        parts.append(
            f"{n_test} {'test' if n_test == 1 else 'tests'} skipped"
        )
    return parts


def _role_line(role_name: str, role_cfg: Any) -> str:
    """Render one role's configuration as a bullet line.

    The target role uses tier routing, so its ``model`` field is ignored
    by the framework; call that out explicitly so readers know why the
    target's model isn't pinned.
    """
    parts: list[str] = [f"provider=`{role_cfg.provider}`"]
    if role_name == "target":
        parts.append("model=_tier routing_")
    elif role_cfg.model:
        parts.append(f"model=`{role_cfg.model}`")
    if role_cfg.auth_mode:
        parts.append(f"auth=`{role_cfg.auth_mode}`")
    return f"- **{role_name}**: " + ", ".join(parts)


def write_summary(
    outputs_dir: Path,
    test_outcomes: dict[str, dict[str, Any]],
    judge_records: dict[str, list[JudgeRecord]],
    config: EvalConfig | None = None,
    total_seconds: float | None = None,
) -> Path:
    """Write ``summary.md`` into *outputs_dir*.  Returns the path written."""
    lines: list[str] = []

    lines.append("# Eval run summary")
    lines.append("")

    # One condensed metadata line — when, how long, how much.  Below
    # this comes the Status section (the actual answer to "did it
    # pass?") and then the per-role Config block.  Keeping the meta
    # tight up here means a reviewer's eye lands on Status without
    # parsing operational metadata first.
    total_cost = sum(
        rec.cost_usd for recs in judge_records.values() for rec in recs
    )
    for folder_rel in {
        _parse_nodeid(n)["folder_rel"]
        for n in list(test_outcomes) + list(judge_records)
        if n != "<unknown>"
    }:
        mod_meta = _load_module_metadata(outputs_dir, folder_rel)
        if mod_meta is not None:
            total_cost += mod_meta.get("cost_usd", 0.0) or 0.0
    meta_parts: list[str] = [
        f"Generated: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
    ]
    if total_seconds is not None:
        meta_parts.append(f"total time: {_format_duration(total_seconds)}")
    if total_cost > 0:
        meta_parts.append(f"cost: ${total_cost:.4f}")
    lines.append(" · ".join(meta_parts))
    lines.append("")

    counts: dict[str, int] = {
        "passed": 0, "failed": 0, "skipped": 0,
        "error": 0, "smoke_failed": 0, "advisory_failed": 0,
        "refused": 0,
    }
    # Number of *tests* that returned at least one N/A verdict.
    # Distinct from ``total_na`` (criterion-level count) — the
    # top-line bucket counts tests that had any N/A criterion, not
    # how many criteria returned N/A.  These tests still PASSED
    # (N/A verdicts don't fail a test); we surface them as a
    # sub-category of "passing" because "criterion didn't apply"
    # is meaningfully different from "criterion fired YES".
    tests_with_na = 0
    for nodeid, outcome in test_outcomes.items():
        key = outcome.get("outcome", "error")
        counts[key] = counts.get(key, 0) + 1
        if key == "passed" and any(
            rec.verdict == "NA" for rec in judge_records.get(nodeid, [])
        ):
            tests_with_na += 1

    # Tests that have judge records but no outcome yet are in flight
    # (pytest entered the test but makereport hasn't recorded a
    # verdict).  Surfacing them lets an interrupted run still show
    # which test was mid-flight and what the judge had already said.
    running_ids: list[str] = sorted(
        tid for tid in judge_records
        if tid not in test_outcomes and tid != "<unknown>"
    )

    # Three test-level outcome buckets, designed to answer "would
    # this run block a launch?" at a glance:
    #
    #   OK             — produced a launch-OK signal: the test
    #                    passed, or it failed-but-was-advisory.
    #                    Tests with N/A verdicts are a sub-category
    #                    of passing.
    #   FAILED         — produced a real blocking failure.  Advisory
    #                    failures are NOT here.
    #   FAILED TO RUN  — produced no meaningful pass/fail signal:
    #                    infra error, smoke-gate failure, or an
    #                    explicit skip.  These need attention because
    #                    the suite has gaps in coverage, but they
    #                    aren't necessarily bugs in the target.
    test_passes_clean = counts["passed"] - tests_with_na
    ok_count = (
        counts["passed"]
        + counts["advisory_failed"]
        + counts["refused"]
    )
    failed_count = counts["failed"]
    failed_to_run_count = (
        counts["error"]
        + counts["smoke_failed"]
        + counts["skipped"]
    )

    # Status: a single "Passed / Failed" verdict the reviewer can
    # see in one glance.  Fails closed: anything that's not a clean
    # OK (real failures, infra errors, smoke gaps, skips) flips the
    # status to Failed because the suite did not produce a complete
    # OK signal.  In-flight tests don't count — an interrupted run
    # is neither passed nor failed yet, so we leave the status off.
    if running_ids and not (failed_count or failed_to_run_count):
        lines.append("## Status: In progress")
    elif failed_count or failed_to_run_count:
        lines.append("## Status: Failed")
    else:
        lines.append("## Status: Passed")
    lines.append("")

    # Render the bullets.  Each bucket is its own line so a
    # reviewer can see the answer to "what should I worry about?"
    # without parsing a fused summary line.  Sub-categories appear
    # in parens; we skip parens entirely if a sub-category is 0 to
    # avoid noise like "(70 passing · 0 N/A · 0 advisory failures)".
    ok_parts: list[str] = []
    if test_passes_clean:
        ok_parts.append(f"{test_passes_clean} passing")
    if tests_with_na:
        ok_parts.append(f"{tests_with_na} N/A")
    if counts["advisory_failed"]:
        ok_parts.append(
            f"{counts['advisory_failed']} advisory failures"
        )
    if counts["refused"]:
        # Tests in modules where the refusal-acceptable gate
        # short-circuited.  The agent declined cleanly, which is
        # the desired outcome for those tests — counted as OK
        # alongside passes, but called out separately so a reader
        # knows which OK tests came from "agent helped" vs.
        # "agent declined."
        ok_parts.append(f"{counts['refused']} refused")
    ok_line = f"- **{ok_count} OK**"
    if ok_parts:
        ok_line += f" ({' · '.join(ok_parts)})"
    lines.append(ok_line)

    if failed_count:
        # Bold the failed line — this is the one that blocks a
        # launch.  Reviewer should see it before they see anything
        # else.
        lines.append(f"- **{failed_count} failed**")

    if failed_to_run_count:
        # The "failed to run" bucket: tests that didn't produce a
        # signal because something upstream stopped them.  Listed
        # by *cause* (smoke-failed module, infra error, skip), and
        # for module-scoped causes counted by module — the per-test
        # count is just module_count × tests-per-module noise that
        # tells the reader less than "3 modules failed their smoke
        # check" does.  Per-gate breakdown lives in the per-module
        # tables further down — we don't repeat it here.
        lines.append(f"- **{failed_to_run_count} failed to run**")
        for sub in _failed_to_run_breakdown(test_outcomes, counts):
            lines.append(f"  - {sub}")

    if running_ids:
        # In-flight tests — pytest entered them but didn't finish.
        # Surfaces interrupted-run state so a reviewer skimming the
        # summary sees what was mid-flight.
        lines.append(f"- {len(running_ids)} still running")
    lines.append("")

    if config is not None and config.roles:
        # Config block sits AFTER status — operational metadata
        # (which model, which provider) is useful but secondary to
        # the pass/fail verdict.  A reviewer only needs to read it
        # if the result looks suspicious.
        lines.append("**Config:**")
        lines.append("")
        for role_name in ("target", "user", "judge"):
            role_cfg = config.roles.get(role_name)
            if role_cfg is not None:
                lines.append(_role_line(role_name, role_cfg))
        # Any other roles the config defines, for forward-compat.
        for role_name, role_cfg in config.roles.items():
            if role_name not in ("target", "user", "judge"):
                lines.append(_role_line(role_name, role_cfg))
        lines.append("")

    # Group nodeids by module (<category>/<module-stem>) so the
    # shared-conversation structure is reflected in the report.
    all_ids: list[str] = list(test_outcomes.keys()) + running_ids
    groups: dict[str, list[str]] = {}
    for nodeid in all_ids:
        parsed = _parse_nodeid(nodeid)
        groups.setdefault(parsed["folder_rel"], []).append(nodeid)
    for module_ids in groups.values():
        module_ids.sort()

    def _outcome_for(nodeid: str) -> dict[str, Any]:
        return test_outcomes.get(
            nodeid, {"outcome": "running", "duration": 0.0, "error": None},
        )

    # --- Results: one mini-table per module ---
    lines.append("## Results")
    lines.append("")
    # ONE big table for all modules.  Markdown auto-sizes columns
    # consistently across all rows of the same table — that solves
    # the "different per-module table widths" readability problem.
    # Module boundaries are marked with bolded "module-header"
    # rows that put the module name + status in the wide Test
    # column; the # / Outcome / Duration / Cost cells are blank
    # for those rows, which renders as a visual span.
    lines.append("| # | Test | Outcome | Duration | Cost |")
    lines.append("| --- | --- | --- | --- | --- |")
    test_index = 1
    sorted_folders = sorted(groups)
    for module_idx, folder_rel in enumerate(sorted_folders):
        module_ids = groups[folder_rel]
        module_outcomes = [_outcome_for(n)["outcome"] for n in module_ids]
        module_na = _count_na_records(module_ids, judge_records)
        module_icon, module_stats = _module_aggregate(
            module_outcomes, na_count=module_na,
        )
        meta = _load_module_metadata(outputs_dir, folder_rel)
        smoke_gate_records = _load_smoke_gate_records(outputs_dir, folder_rel)
        # Link the module-header row to the matching Details anchor
        # so reviewers can jump from the table straight to the
        # per-test breakdown without scrolling.
        details_anchor = _module_anchor(folder_rel)
        # Visual separator between modules — a row of em-dashes
        # in the wide Test column reads as a horizontal rule and
        # makes module starts easy to spot when scrolling.  The
        # other cells stay empty so the rule visually spans the
        # cell width without bleeding into the # column's number
        # alignment.  Skipped before the first module since the
        # table header is right there.
        if module_idx > 0:
            lines.append(
                "| | ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ | | | |"
            )
        # Module-header row.  Bolded module name + stats in the
        # Test column; other cells empty so the bolded text reads
        # as a section divider.
        lines.append(
            f"| | **{module_icon} [`{folder_rel}`](#{details_anchor})"
            f" — {module_stats}** | | | |"
        )
        # Conversation summary row (turns / duration / cost) — same
        # context as before, just inside the unified table.
        if meta is not None:
            lines.append(
                f"| | _conversation_ | "
                f"{meta.get('turn_count', '?')} turns | "
                f"{_format_duration(meta.get('duration_seconds', 0.0))} | "
                f"${meta.get('cost_usd', 0.0):.4f} |"
            )

        # Smoke-gate rows: persona-adoption first (turn-1 gate, runs
        # during converse_with), then smoke check (post-conversation
        # gate).  Always at the top of the per-test rows in
        # run-order, with the 🔬 marker so they don't visually mix
        # with the numbered user assertions.  A separator row below
        # makes the boundary explicit.  Either gate may be missing
        # (persona-adoption skipped on resumed runs; both missing if
        # the cache file isn't there yet) — only render rows for
        # the gates that actually have records.
        rendered_any_gate = False
        for reserved_name, label, rec in smoke_gate_records:
            if rec is None:
                continue
            verdict_icon, verdict_label = _gate_verdict_display(
                reserved_name, rec.verdict,
            )
            duration_cell = (
                f"{rec.elapsed:.1f}s" if rec.elapsed else "—"
            )
            cost_cell = f"${rec.cost_usd:.4f}" if rec.cost_usd > 0 else "—"
            anchor = _smoke_anchor(folder_rel, reserved_name)
            lines.append(
                f"| 🔬 | [**_{label}_**](#{anchor}) | "
                f"{verdict_icon} {verdict_label} | "
                f"{duration_cell} | "
                f"{cost_cell} |"
            )
            rendered_any_gate = True
        if rendered_any_gate and module_ids:
            # Visual separator row between the smoke gates above and
            # the user assertions below.  Markdown tables don't
            # support real horizontal rules between rows, so we use
            # a marker row with bold em-dashes — clear enough to
            # read at a glance without breaking the table grid.
            lines.append("| | **— assertions ↓ —** | | | |")

        for nodeid in module_ids:
            info = _outcome_for(nodeid)
            parsed = _parse_nodeid(nodeid)
            test_icon = _OUTCOME_ICON.get(
                info["outcome"], _OUTCOME_ICON["error"],
            )
            duration = info.get("duration", 0.0)
            duration_cell = (
                f"{duration:.1f}s" if info["outcome"] != "running" else "—"
            )
            # Test cost = sum of judge-call costs made inside it.  If
            # the backend didn't report costs, they stay 0 — render
            # as "—" so it doesn't look like "$0.00 (free!)".
            judge_cost = sum(
                rec.cost_usd for rec in judge_records.get(nodeid, [])
            )
            cost_cell = f"${judge_cost:.4f}" if judge_cost > 0 else "—"
            anchor = _anchor(nodeid)
            test_label = parsed["test_name"] or "(module)"
            # If any of this test's criteria came back N/A, annotate
            # the outcome cell so a reviewer scanning the results
            # table can distinguish "all YES" from "some didn't apply"
            # without having to open the Details section.
            na_count = sum(
                1
                for rec in judge_records.get(nodeid, [])
                if rec.verdict == "NA"
            )
            # Build the outcome label.  For advisory failures, if
            # the marker carried an issue-tracker URL, wrap the
            # "advisory" word itself as the link rather than
            # appending a separate "#NNN" tag onto the test name —
            # the advisory-tracking semantic IS the outcome, so
            # making the outcome word the link reads more naturally.
            outcome_label = _test_outcome_label(info["outcome"])
            issue_url = info.get("advisory_issue") if (
                info["outcome"] == "advisory_failed"
            ) else None
            if issue_url:
                outcome_label = f"[{outcome_label}]({issue_url})"
            outcome_cell = f"{test_icon} {outcome_label}"
            if na_count and info["outcome"] == "passed":
                outcome_cell += f" ({_VERDICT_ICON['NA']} {na_count})"
            test_name_cell = f"[`{test_label}`](#{anchor})"
            lines.append(
                f"| {test_index} | {test_name_cell} | "
                f"{outcome_cell} | "
                f"{duration_cell} | "
                f"{cost_cell} |"
            )
            test_index += 1
    lines.append("")

    # --- Details: one section per module, per-test sub-sections inside ---
    lines.append("## Details")
    lines.append("")
    test_index = 1
    for folder_rel in sorted(groups):
        module_ids = groups[folder_rel]
        module_outcomes = [_outcome_for(n)["outcome"] for n in module_ids]
        module_na = _count_na_records(module_ids, judge_records)
        module_icon, module_stats = _module_aggregate(
            module_outcomes, na_count=module_na,
        )
        # Match the Results heading: append the failing gate name
        # when the module has any smoke_failed tests.
        smoke_gate_records = _load_smoke_gate_records(outputs_dir, folder_rel)
        if "smoke_failed" in module_outcomes:
            gate_label = _failing_gate_label(smoke_gate_records)
            if gate_label is not None:
                module_stats += f" ({gate_label} gate failed)"
        meta = _load_module_metadata(outputs_dir, folder_rel)
        # Anchor target for the Results-section link.  Placed inline
        # with the heading so the HTML id attaches to the section
        # start, not to trailing content below.
        details_anchor = _module_anchor(folder_rel)
        lines.append(
            f'### <a id="{details_anchor}"></a>{module_icon} '
            f"`{folder_rel}` — {module_stats}"
        )
        lines.append("")
        if meta is not None:
            notes: list[str] = []
            if meta.get("stopped_early"):
                notes.append("stopped early")
            if meta.get("timed_out"):
                notes.append("timed out")
            note_suffix = (" · " + ", ".join(notes)) if notes else ""
            lines.append(
                f"**Conversation:** {meta.get('turn_count', '?')} turns · "
                f"${meta.get('cost_usd', 0.0):.4f} · "
                f"{_format_duration(meta.get('duration_seconds', 0.0))}"
                f"{note_suffix}"
            )
            lines.append("")
        lines.append(
            f"**Artifacts:** [folder](./{folder_rel}/) · "
            f"[transcript](./{folder_rel}/transcript.md) · "
            f"[protocol/](./{folder_rel}/.clarity-protocol/) · "
            f"[clarity transcripts](./{folder_rel}/.clarity-protocol/transcripts/)"
        )
        lines.append("")

        # Smoke-failure banner.  One conversation ⇒ one smoke
        # verdict, so the failure reasoning only needs to appear
        # once at the module level even though every test in the
        # module carries the ``smoke_failed`` outcome.  Both the
        # turn-1 persona-adoption gate and the post-conversation
        # smoke gate raise SmokeCheckFailedError, so the banner text
        # stays generic — the per-gate detail subsections below
        # show the actual judge record and reasoning.
        smoke_reasoning = _first_smoke_reasoning(module_ids, test_outcomes)
        if smoke_reasoning:
            lines.append(
                f"{_OUTCOME_ICON['smoke_failed']} **Smoke gate failed — "
                "module aborted.**  One of the framework's two smoke "
                "checks rejected this run; subsequent test assertions "
                "were not run.  See the smoke-check detail below for "
                "which gate fired and why."
            )
            lines.append("")

        # Per-gate detail subsections.  Renders both gates that have
        # records on disk (regardless of pass/fail) at the top of
        # each module's detail section, before the scenario block
        # and the user-test sections.  These are the most
        # information-dense judge calls in the run and worth
        # surfacing prominently.  ``smoke_gate_records`` was loaded
        # above for the heading qualifier; reuse it here.
        for reserved_name, label, rec in smoke_gate_records:
            if rec is None:
                continue
            anchor = _smoke_anchor(folder_rel, reserved_name)
            verdict_icon, verdict_label = _gate_verdict_display(
                reserved_name, rec.verdict,
            )
            elapsed_str = (
                f" _(judge took {rec.elapsed:.1f}s)_" if rec.elapsed else ""
            )
            lines.append(
                f'#### <a id="{anchor}"></a>🔬 {label}'
            )
            lines.append("")
            lines.append(
                f"{verdict_icon} **{verdict_label}**{elapsed_str}"
            )
            lines.append("")
            lines.append(f"**Criterion:** {_truncate(rec.claim, 1000)}")
            lines.append("")
            if rec.reasoning:
                lines.append(f"**Reasoning:** {rec.reasoning}")
                lines.append("")

        if meta is not None:
            lines.extend(_render_scenario_block(meta))

        for nodeid in module_ids:
            info = _outcome_for(nodeid)
            parsed = _parse_nodeid(nodeid)
            records = judge_records.get(nodeid, [])
            test_icon = _OUTCOME_ICON.get(
                info["outcome"], _OUTCOME_ICON["error"],
            )
            anchor = _anchor(nodeid)
            test_label = parsed["test_name"] or "(module)"

            lines.append(
                f'#### <a id="{anchor}"></a>{test_icon} {test_index}: `{test_label}`'
            )
            lines.append("")
            test_index += 1

            # Issue-tracker link for advisory failures.  Rendered
            # right under the heading so reviewers see the tracking
            # context before the judge reasoning — useful when the
            # issue contains broader notes that explain WHY this
            # criterion is currently aspirational.
            issue_url = info.get("advisory_issue") if (
                info["outcome"] == "advisory_failed"
            ) else None
            if issue_url:
                lines.append(
                    f"**Tracked in:** {_format_issue_link_long(issue_url)}"
                )
                lines.append("")

            if records:
                lines.append("**Judge evaluations:**")
                lines.append("")
                for i, rec in enumerate(records, 1):
                    verdict_icon = _verdict_icon(rec.verdict)
                    # NA reads better with a "/" in the bold label even
                    # though we store the canonical "NA" form internally.
                    verdict_label = "N/A" if rec.verdict == "NA" else rec.verdict
                    claim = _truncate(rec.claim, 1000)
                    reasoning = rec.reasoning  # Don't truncate this
                    if rec.cached:
                        elapsed_str = " _(cached)_"
                    elif rec.elapsed:
                        elapsed_str = f" _(judge took {rec.elapsed:.1f}s)_"
                    else:
                        elapsed_str = ""
                    lines.append(
                        f"{i}. {verdict_icon} **{verdict_label}**{elapsed_str}"
                    )
                    lines.append("")
                    lines.append(f"   **Criterion:** {claim}")
                    lines.append("")
                    if reasoning:
                        lines.append(f"   **Reasoning:** {reasoning}")
                        lines.append("")

            # Only render infrastructure errors.  Assertion tracebacks
            # are mostly noise — the judge's verdict + reasoning above
            # already tells you *why* the test failed substantively,
            # and the Python-level traceback adds little beyond that.
            is_infra = info.get("error_type") == "infra"
            if info["outcome"] == "failed" and info.get("error") and is_infra:
                lines.append("**Infrastructure error (full traceback):**")
                lines.append("")
                lines.append("```")
                lines.append(info["error"])
                lines.append("```")
                lines.append("")

    summary_path = outputs_dir / "summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path
