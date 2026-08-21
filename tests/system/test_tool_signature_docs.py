"""Tool-signature introspection tests (sprint 031 ticket 006).

The sprint 031 review found docs claiming call signatures that
disagree with the real, registered MCP tools -- e.g. some docs say
``move_ticket_to_done(sprint_id, ticket_id)`` and
``reconcile_worktrees(repo_root, sprint_dir)``, but the tools actually
registered on the MCP server take a single argument each
(``move_ticket_to_done(path)``, ``reconcile_worktrees(sprint_id)``).
``reconcile_worktrees`` is a case of exactly this: the registered MCP
tool in ``tools/artifact_tools.py`` takes only ``sprint_id`` and
internally calls the *different*, two-argument
``clasi.worktree.reconcile_worktrees(repo_root, sprint_dir)`` helper --
a doc that describes the internal helper's arguments as if they were
the MCP tool's own is silently wrong.

This suite introspects the live MCP tool registry (via
``inspect.signature``, following FastMCP's ``_tool_manager._tools``)
rather than hardcoding an expected signature, so it keeps working if a
tool's real signature changes. ``TestScannerCatchesKnownMismatch``
proves the scanner isn't vacuous by feeding it a reproduction of the
exact wrong text the review found. ``TestDocsThisTicketTouchesAgree``
then runs the same scanner over the docs this ticket actually modifies.

Known, deliberately out-of-scope drift: ``plugin/agents/team-lead/agent.md``
still says ``move_ticket_to_done(sprint_id, ticket_id)`` (confirmed by
running this scanner over it by hand during ticket 006 -- see the
ticket's implementation notes). Fixing that file is sprint 031 ticket
007's scope (the prose-consolidation half), so it is deliberately not
scanned by this suite -- scanning it here would make ticket 006's own
tests fail for a bug ticket 006 was told not to fix.
"""

import inspect
import re

import clasi.tools.artifact_tools  # noqa: F401  (registers MCP tools)
import clasi.tools.design_tools  # noqa: F401  (registers MCP tools)
import clasi.tools.process_tools  # noqa: F401  (registers MCP tools)
from clasi.mcp_server import content_path, server
from clasi.platforms._rules import SOURCE_CODE_BODY

# Matches a markdown inline-code span that looks like a call:
# `some_name(arg1, arg2)`. Deliberately requires the surrounding
# backticks so prose mentions of a bare tool name (no parens, e.g.
# "`move_ticket_to_done`") are not treated as a signature claim.
_CALL_PATTERN = re.compile(r"`(\w+)\(([^)]*)\)`")

CHECKED_TOOLS = ("move_ticket_to_done", "reconcile_worktrees")


def _registered_arity(tool_name: str) -> int:
    """Return the introspected parameter count for a registered MCP tool.

    Reads straight from the live FastMCP tool registry
    (``server._tool_manager._tools``), the same mechanism
    ``tests/unit/test_mcp_server.py`` uses to enumerate tools --
    ``inspect.signature`` follows ``__wrapped__`` (set by
    ``@functools.wraps`` inside ``@clasi_tool``) automatically, so this
    reflects the real tool function's parameters, not the decorator's.
    """
    tools = server._tool_manager._tools
    assert tool_name in tools, f"'{tool_name}' is not a registered MCP tool"
    fn = tools[tool_name].fn
    return len(inspect.signature(fn).parameters)


def _claimed_arities(text: str, tool_name: str) -> list[int]:
    """Find every `` `tool_name(...)` `` code span in *text* and return
    the argument count each occurrence claims."""
    arities = []
    for match in _CALL_PATTERN.finditer(text):
        if match.group(1) != tool_name:
            continue
        args = match.group(2).strip()
        arities.append(0 if not args else len(args.split(",")))
    return arities


class TestIntrospectedSignatures:
    """Lock in the real, live signatures for the two tools named in the
    sprint 031 review's contradiction table."""

    def test_move_ticket_to_done_is_single_argument(self):
        assert _registered_arity("move_ticket_to_done") == 1

    def test_reconcile_worktrees_is_single_argument(self):
        assert _registered_arity("reconcile_worktrees") == 1


class TestScannerCatchesKnownMismatch:
    """Prove the scanner is not vacuous: it must flag a reproduction of
    the exact wrong-signature text the sprint 031 review found (in
    plugin/agents/team-lead/agent.md and elsewhere), even though this
    suite deliberately does not scan that file itself (see module
    docstring)."""

    def test_flags_move_ticket_to_done_two_arg_example(self):
        bad_doc = "5. `move_ticket_to_done(sprint_id, ticket_id)` is called"
        claimed = _claimed_arities(bad_doc, "move_ticket_to_done")
        assert claimed == [2]
        assert claimed[0] != _registered_arity("move_ticket_to_done")

    def test_flags_reconcile_worktrees_two_arg_example(self):
        bad_doc = "Calls `reconcile_worktrees(repo_root, sprint_dir)` internally."
        claimed = _claimed_arities(bad_doc, "reconcile_worktrees")
        assert claimed == [2]
        assert claimed[0] != _registered_arity("reconcile_worktrees")

    def test_does_not_flag_a_correct_single_arg_example(self):
        good_doc = "`move_ticket_to_done(path)` | Move completed ticket to done/"
        claimed = _claimed_arities(good_doc, "move_ticket_to_done")
        assert claimed == [1]
        assert claimed[0] == _registered_arity("move_ticket_to_done")

    def test_ignores_bare_name_with_no_parens(self):
        """A bare `` `move_ticket_to_done` `` mention (no call syntax)
        is not a signature claim and must not be flagged."""
        prose = "Only an MCP call (e.g. `update_ticket_status`, `move_ticket_to_done`) moves a ticket."
        assert _claimed_arities(prose, "move_ticket_to_done") == []


class TestDocsThisTicketTouchesAgree:
    """AC #5: no doc this ticket modifies states a signature for
    move_ticket_to_done or reconcile_worktrees that disagrees with the
    introspected one."""

    def _assert_no_disagreement(self, text: str, source_label: str) -> None:
        for tool_name in CHECKED_TOOLS:
            real_arity = _registered_arity(tool_name)
            for claimed_arity in _claimed_arities(text, tool_name):
                assert claimed_arity == real_arity, (
                    f"{source_label} claims {tool_name} takes "
                    f"{claimed_arity} arg(s); the registered MCP tool "
                    f"actually takes {real_arity}"
                )

    def test_rules_source_code_body(self):
        """platforms/_rules.py's SOURCE_CODE_BODY -- canonical source
        for the installed .claude/rules/source-code.md."""
        self._assert_no_disagreement(SOURCE_CODE_BODY, "_rules.SOURCE_CODE_BODY")

    def test_process_tools_source(self):
        """tools/process_tools.py's own docstrings/comments."""
        import clasi.tools.process_tools as pt

        source = inspect.getsource(pt)
        self._assert_no_disagreement(source, "tools/process_tools.py")

    def test_dispatch_subagent_skill(self):
        """plugin/skills/dispatch-subagent/SKILL.md, rewritten by this
        ticket to drop the log_subagent_dispatch/update_dispatch_log
        mandate."""
        skill_path = content_path("plugin", "skills", "dispatch-subagent", "SKILL.md")
        text = skill_path.read_text(encoding="utf-8")
        self._assert_no_disagreement(text, "dispatch-subagent/SKILL.md")
