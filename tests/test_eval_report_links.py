"""Tests for Results → Details anchor linking in the eval summary.

The summary is long when there are many modules, and reviewers
typically scan the Results table first and then jump into the
matching Details subsection for the module that caught their eye.
The Results headings are markdown links that target stable anchors
on the Details headings — the navigation depends on both halves
being present and matching.
"""

from __future__ import annotations

import re
from pathlib import Path

from evals.framework.judge import JudgeRecord
from evals.framework.report import _module_anchor, write_summary


def test_module_anchor_is_stable_and_sanitized() -> None:
    """Path separators and dots map to dashes; prefix is ``module-``.

    Determinism is important because the Results link and the Details
    anchor are generated in two places; if they produce different
    strings the link navigates to nothing.
    """
    a = _module_anchor("functionality/test_add_ai_to_product")
    b = _module_anchor("functionality/test_add_ai_to_product")
    assert a == b  # deterministic
    assert a.startswith("module-")
    assert "/" not in a  # path separator sanitized
    assert a == "module-functionality-test_add_ai_to_product"


def test_results_heading_links_to_details_anchor(tmp_path: Path) -> None:
    """A module's Results heading is a markdown link to its Details anchor.

    The same call to ``_module_anchor`` produces both the link target
    (in Results) and the anchor ID (in Details), so the two halves
    are guaranteed to match.  We verify that by inspecting the
    rendered summary: the link target appears in the Results section,
    and the matching ``<a id=...>`` appears in the Details section.
    """
    folder_rel = "functionality/test_example"
    test_outcomes = {
        f"evals/cases/{folder_rel}.py::t1": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
    }
    judge_records: dict[str, list[JudgeRecord]] = {}
    write_summary(tmp_path, test_outcomes, judge_records)

    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    expected_anchor = _module_anchor(folder_rel)

    # Results section has a link to the anchor.
    link_re = rf"\]\(#{re.escape(expected_anchor)}\)"
    assert re.search(link_re, text), (
        f"Results heading must link to #{expected_anchor}"
    )
    # Details section has the matching anchor element.
    anchor_re = rf'<a id="{re.escape(expected_anchor)}"></a>'
    assert re.search(anchor_re, text), (
        f"Details heading must carry the {expected_anchor} anchor"
    )


def test_each_module_gets_its_own_anchor(tmp_path: Path) -> None:
    """Multiple modules → multiple distinct anchors, no collisions."""
    test_outcomes = {
        "evals/cases/safety/test_alpha.py::t1": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
        "evals/cases/functionality/test_beta.py::t1": {
            "outcome": "passed", "duration": 0.1, "error": None,
        },
    }
    write_summary(tmp_path, test_outcomes, {})
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")

    alpha = _module_anchor("safety/test_alpha")
    beta = _module_anchor("functionality/test_beta")
    assert alpha != beta
    assert f'<a id="{alpha}"></a>' in text
    assert f'<a id="{beta}"></a>' in text
    assert f"](#{alpha})" in text
    assert f"](#{beta})" in text
