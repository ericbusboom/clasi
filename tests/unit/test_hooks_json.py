"""Tests for the packaged plugin hooks.json content (sprint 026 / ticket 004).

Covers two independent AC items directly against the source-of-truth
file (src/clasi/plugin/hooks/hooks.json), which the Claude platform
installer (clasi.platforms.claude) copies wholesale into a target
project's .claude/settings.json (see tests/unit/test_init_command.py's
TestHooksConfig for the installed-fixture assertions):

1. commit-check (PostToolUse/Bash), TaskCreated, and TaskCompleted are
   removed — 0 of 2,447 logged hook events, ever.
2. Every remaining registration carries an explicit "timeout" value.
"""

import json
from pathlib import Path

_HOOKS_JSON = (
    Path(__file__).resolve().parents[2]
    / "src" / "clasi" / "plugin" / "hooks" / "hooks.json"
)


def _load_hooks_data() -> dict:
    return json.loads(_HOOKS_JSON.read_text(encoding="utf-8"))


def _all_hook_commands(hooks_data: dict) -> list[dict]:
    """Flatten every individual {"type": ..., "command": ..., ...} entry
    across every event type and matcher group."""
    commands = []
    for entries in hooks_data.get("hooks", {}).values():
        for entry in entries:
            commands.extend(entry.get("hooks", []))
    return commands


class TestDeadRegistrationsRemoved:
    def test_hooks_json_file_exists(self):
        assert _HOOKS_JSON.exists(), f"expected hooks.json at {_HOOKS_JSON}"

    def test_task_created_event_absent(self):
        """The TaskCreated event key itself is gone, not just emptied —
        an empty list would still be a (harmless) registration; the
        AC is that the event key is absent entirely."""
        data = _load_hooks_data()
        assert "TaskCreated" not in data["hooks"]

    def test_task_completed_event_absent(self):
        data = _load_hooks_data()
        assert "TaskCompleted" not in data["hooks"]

    def test_commit_check_command_absent(self):
        """commit-check was one matcher group within PostToolUse (which
        also carries plan-to-issue) — assert no registered command
        anywhere invokes it, not that the whole PostToolUse key is gone."""
        data = _load_hooks_data()
        commands = [c.get("command", "") for c in _all_hook_commands(data)]
        assert not any("commit-check" in cmd for cmd in commands)

    def test_post_tool_use_still_has_plan_to_issue(self):
        """Regression: removing commit-check's matcher group from
        PostToolUse must not have taken plan-to-issue down with it."""
        data = _load_hooks_data()
        commands = [c.get("command", "") for c in _all_hook_commands(data)]
        assert any("plan-to-issue" in cmd for cmd in commands)

    def test_no_leftover_task_or_commit_check_commands_anywhere(self):
        """Belt-and-suspenders: no registered command string anywhere in
        the file references the removed events by name, regardless of
        which event key it might have been filed under."""
        data = _load_hooks_data()
        commands = [c.get("command", "") for c in _all_hook_commands(data)]
        for cmd in commands:
            assert "task-created" not in cmd
            assert "task-completed" not in cmd
            assert "commit-check" not in cmd


class TestExplicitTimeouts:
    def test_every_registration_has_a_timeout(self):
        data = _load_hooks_data()
        commands = _all_hook_commands(data)
        assert commands, "expected at least one hook command registered"
        missing = [c for c in commands if "timeout" not in c]
        assert not missing, f"registrations missing an explicit timeout: {missing}"

    def test_timeouts_are_positive_numbers(self):
        data = _load_hooks_data()
        for cmd in _all_hook_commands(data):
            timeout = cmd["timeout"]
            assert isinstance(timeout, (int, float)) and timeout > 0, (
                f"non-positive or non-numeric timeout in {cmd}"
            )


class TestSurvivingRegistrationsIntact:
    """Regression: the trim must not have removed anything it wasn't
    supposed to."""

    def test_role_guard_still_registered(self):
        data = _load_hooks_data()
        commands = [c.get("command", "") for c in _all_hook_commands(data)]
        assert any("role-guard" in cmd for cmd in commands)

    def test_mcp_guard_still_registered(self):
        data = _load_hooks_data()
        commands = [c.get("command", "") for c in _all_hook_commands(data)]
        assert any("mcp-guard" in cmd for cmd in commands)

    def test_status_inject_still_registered(self):
        data = _load_hooks_data()
        commands = [c.get("command", "") for c in _all_hook_commands(data)]
        assert any("status-inject" in cmd for cmd in commands)

    def test_subagent_start_and_stop_still_registered(self):
        data = _load_hooks_data()
        commands = [c.get("command", "") for c in _all_hook_commands(data)]
        assert any("subagent-start" in cmd for cmd in commands)
        assert any("subagent-stop" in cmd for cmd in commands)
