"""Tests for the plan_to_todo module."""

import json
import time
from pathlib import Path

import pytest

from clasi.plan_to_todo import plan_to_todo


def _make_plan_file(plans_dir: Path, name: str = "my-plan.md", content: str = "# My Plan\n\nSome content.") -> Path:
    plans_dir.mkdir(parents=True, exist_ok=True)
    p = plans_dir / name
    p.write_text(content, encoding="utf-8")
    return p


class TestPlanToTodoSignature:
    def test_no_payload_omits_debug_block(self, tmp_path):
        """When hook_payload is None (default), no debug block is appended."""
        plans_dir = tmp_path / "plans"
        todo_dir = tmp_path / "todo"
        _make_plan_file(plans_dir)

        result = plan_to_todo(plans_dir, todo_dir)

        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert "Hook Debug Info" not in content

    def test_with_payload_appends_debug_block(self, tmp_path):
        """When hook_payload is provided, a ## Hook Debug Info block is appended."""
        plans_dir = tmp_path / "plans"
        todo_dir = tmp_path / "todo"
        _make_plan_file(plans_dir)
        payload = {"hook_event_name": "PostToolUse", "tool_name": "ExitPlanMode"}

        result = plan_to_todo(plans_dir, todo_dir, hook_payload=payload)

        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert "## Hook Debug Info" in content

    def test_debug_block_contains_payload(self, tmp_path):
        """The debug block JSON includes the hook_payload key."""
        plans_dir = tmp_path / "plans"
        todo_dir = tmp_path / "todo"
        _make_plan_file(plans_dir)
        payload = {"hook_event_name": "PostToolUse", "tool_name": "ExitPlanMode"}

        result = plan_to_todo(plans_dir, todo_dir, hook_payload=payload)

        assert result is not None
        content = result.read_text(encoding="utf-8")
        # Extract the JSON from the fenced code block
        assert '"hook_payload"' in content
        assert '"PostToolUse"' in content

    def test_debug_block_contains_env_keys(self, tmp_path):
        """The debug block JSON includes known env keys."""
        plans_dir = tmp_path / "plans"
        todo_dir = tmp_path / "todo"
        _make_plan_file(plans_dir)

        result = plan_to_todo(plans_dir, todo_dir, hook_payload={})

        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert '"TOOL_INPUT"' in content
        assert '"SESSION_ID"' in content
        assert '"CLASI_AGENT_TIER"' in content

    def test_debug_block_contains_plans_dir_and_plan_file(self, tmp_path):
        """The debug block JSON includes plans_dir and plan_file paths."""
        plans_dir = tmp_path / "plans"
        todo_dir = tmp_path / "todo"
        _make_plan_file(plans_dir, name="alpha.md")

        result = plan_to_todo(plans_dir, todo_dir, hook_payload={})

        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert '"plans_dir"' in content
        assert '"plan_file"' in content
        assert "alpha.md" in content

    def test_empty_payload_dict_appends_debug_block(self, tmp_path):
        """An empty dict payload (not None) still triggers the debug block."""
        plans_dir = tmp_path / "plans"
        todo_dir = tmp_path / "todo"
        _make_plan_file(plans_dir)

        result = plan_to_todo(plans_dir, todo_dir, hook_payload={})

        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert "## Hook Debug Info" in content

    def test_returns_none_when_plans_dir_missing(self, tmp_path):
        """Returns None when the plans directory does not exist."""
        plans_dir = tmp_path / "nonexistent"
        todo_dir = tmp_path / "todo"

        result = plan_to_todo(plans_dir, todo_dir, hook_payload={"foo": "bar"})

        assert result is None

    def test_debug_block_is_valid_json(self, tmp_path):
        """The fenced JSON in the debug block parses successfully."""
        plans_dir = tmp_path / "plans"
        todo_dir = tmp_path / "todo"
        _make_plan_file(plans_dir)
        payload = {"hook_event_name": "PostToolUse"}

        result = plan_to_todo(plans_dir, todo_dir, hook_payload=payload)

        assert result is not None
        content = result.read_text(encoding="utf-8")
        # Extract JSON between ```json ... ```
        start = content.index("```json\n") + len("```json\n")
        end = content.index("\n```", start)
        json_str = content[start:end]
        parsed = json.loads(json_str)
        assert parsed["hook_payload"] == payload
        assert "env" in parsed
        assert "plans_dir" in parsed
        assert "plan_file" in parsed
        assert "cwd" in parsed


class TestPlanToTodoPlanFileParam:
    def test_uses_plan_file_when_provided(self, tmp_path):
        """When plan_file is provided, that specific file is used regardless of mtime."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir(parents=True)
        todo_dir = tmp_path / "todo"

        older = plans_dir / "older-plan.md"
        older.write_text("# Older Plan\n\nOlder content.", encoding="utf-8")
        # Ensure newer has a later mtime
        time.sleep(0.01)
        newer = plans_dir / "newer-plan.md"
        newer.write_text("# Newer Plan\n\nNewer content.", encoding="utf-8")

        result = plan_to_todo(plans_dir, todo_dir, plan_file=older)

        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert "Older Plan" in content
        assert "Newer Plan" not in content

    def test_plan_file_is_deleted_after_conversion(self, tmp_path):
        """The specific plan_file is deleted after conversion."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir(parents=True)
        todo_dir = tmp_path / "todo"

        plan = plans_dir / "specific.md"
        plan.write_text("# Specific Plan\n\nContent.", encoding="utf-8")

        result = plan_to_todo(plans_dir, todo_dir, plan_file=plan)

        assert result is not None
        assert not plan.exists()

    def test_returns_none_when_plan_file_missing(self, tmp_path):
        """Returns None when plan_file points to a non-existent file."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir(parents=True)
        todo_dir = tmp_path / "todo"
        nonexistent = tmp_path / "ghost.md"

        result = plan_to_todo(plans_dir, todo_dir, plan_file=nonexistent)

        assert result is None

    def test_falls_back_to_mtime_when_plan_file_none(self, tmp_path):
        """When plan_file=None, the newest file in plans_dir is used."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir(parents=True)
        todo_dir = tmp_path / "todo"

        older = plans_dir / "alpha.md"
        older.write_text("# Alpha Plan\n\nOlder.", encoding="utf-8")
        time.sleep(0.01)
        newer = plans_dir / "beta.md"
        newer.write_text("# Beta Plan\n\nNewer.", encoding="utf-8")

        result = plan_to_todo(plans_dir, todo_dir, plan_file=None)

        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert "Beta Plan" in content
        assert "Alpha Plan" not in content

    def test_plan_file_ignores_plans_dir_when_provided(self, tmp_path):
        """When plan_file is outside plans_dir, it is still converted correctly."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir(parents=True)
        todo_dir = tmp_path / "todo"

        outside = tmp_path / "external-plan.md"
        outside.write_text("# External Plan\n\nContent from outside.", encoding="utf-8")

        result = plan_to_todo(plans_dir, todo_dir, plan_file=outside)

        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert "External Plan" in content
        assert not outside.exists()
