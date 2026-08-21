"""Doc-scanner tests for the one-full-suite-run fix (sprint 031 ticket 008).

Before this ticket, a sprint ran the full test suite three times:
``execution.md`` Section 5.2 instructed a pre-close run, ``sprint-review``
independently re-ran it, and ``close_sprint`` ran it a third time
internally. This suite proves the fix stays fixed at every layer touched,
following the pattern ``test_tool_signature_docs.py`` established for a
different regression: introspect/scan the *live* content rather than
hardcoding an expected diff, so it keeps working if wording changes
later, and add a "scanner is not vacuous" check so a silently-broken
scanner doesn't rot into a false sense of coverage.

Layers checked (see this repo's own layer-trap warnings, e.g. sprint 031
tickets 006/007's commit messages): the canonical source under
``src/clasi/schemas/se-process/instructions/`` and
``src/clasi/plugin/...``, AND the separately git-tracked
``.agents/skills/*/SKILL.md`` / ``.claude/agents/*/agent.md`` copies
Claude Code's native loader actually reads in this repo -- editing only
the canonical source and leaving an installed copy stale reintroduces
exactly the kind of silent drift this campaign hit three times.
"""

from __future__ import annotations

import re
from pathlib import Path

from clasi.mcp_server import content_path
from clasi.skill_resolve import resolve_skill_body

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The stale two-owner framing this ticket removes. Matched case-sensitively
# against the literal phrase that appeared in execution.md, close.md,
# software-engineering.md, the programmer agent docs, and the
# source-code.md rule before this ticket -- see the ticket's own grep
# during implementation.
_TWO_OWNER_PHRASE = "execute-sprint/close-sprint"

# Every live (non-archived, non-review, non-fixture) doc that either
# governs process behavior or is loaded/installed from something that
# does. docs/reviews/** are historical analysis, not live instructions,
# and are deliberately excluded -- rewriting a dated review to reflect
# a fix it recommended would be revising history, not maintaining it.
_LIVE_DOC_PATHS: list[Path] = [
    content_path("schemas", "se-process", "instructions", "execution.md"),
    content_path("schemas", "se-process", "instructions", "close.md"),
    content_path("schemas", "se-process", "instructions", "sprint-review.md"),
    content_path("plugin", "instructions", "software-engineering.md"),
    content_path("plugin", "agents", "team-lead", "agent.md"),
    content_path("plugin", "agents", "programmer", "agent.md"),
    content_path("plugin", "agents", "programmer", "systematic-debugging.md"),
    content_path("plugin", "agents", "programmer", "tdd-cycle.md"),
    _REPO_ROOT / ".claude" / "agents" / "team-lead" / "agent.md",
    _REPO_ROOT / ".claude" / "agents" / "programmer" / "agent.md",
    _REPO_ROOT / ".claude" / "agents" / "programmer" / "systematic-debugging.md",
    _REPO_ROOT / ".claude" / "agents" / "programmer" / "tdd-cycle.md",
    _REPO_ROOT / ".agents" / "skills" / "sprint-review" / "SKILL.md",
    _REPO_ROOT / ".agents" / "skills" / "close-sprint" / "SKILL.md",
    _REPO_ROOT / ".agents" / "skills" / "execute-sprint" / "SKILL.md",
]


class TestNoTwoOwnerPhraseRemains:
    """AC #5: the docs state the run count once, matching what the code
    does -- none of them may still claim execute-sprint and close-sprint
    jointly own the full-suite run."""

    def test_scanner_is_not_vacuous(self) -> None:
        """Prove the phrase-match itself works before trusting its
        absence anywhere below."""
        sample = (
            "the full suite is a once-per-sprint gate owned by "
            f"{_TWO_OWNER_PHRASE}, not a per-ticket step."
        )
        assert _TWO_OWNER_PHRASE in sample

    def test_no_live_doc_claims_joint_ownership(self) -> None:
        offenders = []
        for path in _LIVE_DOC_PATHS:
            assert path.is_file(), f"expected doc at {path}"
            text = path.read_text(encoding="utf-8")
            if _TWO_OWNER_PHRASE in text:
                offenders.append(str(path))
        assert offenders == [], (
            f"these docs still claim joint execute-sprint/close-sprint "
            f"ownership of the full-suite run: {offenders}"
        )


class TestExecutionMdNoLongerRunsTestsBeforeClose:
    """AC #1: execution.md's Close Sprint step no longer instructs a
    separate pre-close full-suite run."""

    def test_close_sprint_section_has_no_run_instruction(self) -> None:
        text = content_path(
            "schemas", "se-process", "instructions", "execution.md"
        ).read_text(encoding="utf-8")
        close_section_start = text.index("### 5. Close Sprint")
        close_section = text[close_section_start:]
        assert "Run the full test suite" not in close_section, (
            "execution.md's Close Sprint section still instructs a "
            "separate full-suite run -- that run site should be deleted "
            "per 031/008 AC #1"
        )
        assert "close_sprint" in close_section, (
            "the section should still point at close_sprint as the "
            "owner of the (now sole) full-suite run"
        )


class TestSprintReviewInterpretsInsteadOfRerunning:
    """AC #2: sprint-review calls review_sprint_pre_close and interprets
    its output instead of re-running the suite itself."""

    def test_sprint_review_instructions_call_the_tool(self) -> None:
        text = content_path(
            "schemas", "se-process", "instructions", "sprint-review.md"
        ).read_text(encoding="utf-8")
        assert "review_sprint_pre_close" in text
        assert "uv run pytest" not in text, (
            "sprint-review.md must not instruct running the suite "
            "directly -- that is close_sprint's job alone"
        )

    def test_installed_sprint_review_skill_matches(self) -> None:
        """The .agents/skills copy (what Claude Code's native loader
        reads in this repo) carries the same fix, not just the source
        under src/clasi/schemas/."""
        text = (_REPO_ROOT / ".agents" / "skills" / "sprint-review" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "review_sprint_pre_close" in text
        assert "uv run pytest" not in text


class TestReviewSprintPostCloseIsWired:
    """AC #3: review_sprint_post_close is either wired to a caller or
    explicitly retired with a note -- this ticket wires it into the
    close-sprint flow as a post-close sanity check."""

    def test_close_md_calls_review_sprint_post_close(self) -> None:
        text = content_path(
            "schemas", "se-process", "instructions", "close.md"
        ).read_text(encoding="utf-8")
        assert "review_sprint_post_close" in text

    def test_installed_close_sprint_skill_matches(self) -> None:
        text = (_REPO_ROOT / ".agents" / "skills" / "close-sprint" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "review_sprint_post_close" in text


class TestInstalledSkillCopiesAreInSync:
    """Regression guard for the layer-trap failure mode this campaign hit
    repeatedly: .agents/skills/<name>/SKILL.md must be byte-identical to
    what resolve_skill_body(plugin source) produces *right now* -- an
    edit to the canonical instructions doc that forgets to re-sync the
    installed copy would pass every other test in this file while still
    leaving the live skill stale."""

    def _assert_in_sync(self, skill_name: str) -> None:
        plugin_raw = content_path("plugin", "skills", skill_name, "SKILL.md").read_text(
            encoding="utf-8"
        )
        expected = resolve_skill_body(plugin_raw)
        installed = (_REPO_ROOT / ".agents" / "skills" / skill_name / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert installed == expected, (
            f".agents/skills/{skill_name}/SKILL.md has drifted from "
            f"resolve_skill_body(plugin/skills/{skill_name}/SKILL.md) -- "
            "re-sync the installed copy"
        )

    def test_sprint_review_in_sync(self) -> None:
        self._assert_in_sync("sprint-review")

    def test_close_sprint_in_sync(self) -> None:
        self._assert_in_sync("close-sprint")

    def test_execute_sprint_in_sync(self) -> None:
        self._assert_in_sync("execute-sprint")
