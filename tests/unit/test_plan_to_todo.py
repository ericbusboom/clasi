"""Tests for the plan_to_todo module."""

import time
from pathlib import Path

import pytest

from clasi.plan_to_todo import _content_hash, plan_to_todo, plan_to_todo_from_text


def _make_plan_file(plans_dir: Path, name: str = "my-plan.md", content: str = "# My Plan\n\nSome content.") -> Path:
    plans_dir.mkdir(parents=True, exist_ok=True)
    p = plans_dir / name
    p.write_text(content, encoding="utf-8")
    return p


class TestPlanToTodoBasic:
    def test_no_debug_block_in_output(self, tmp_path):
        """Output TODO should not contain any debug block."""
        plans_dir = tmp_path / "plans"
        todo_dir = tmp_path / "todo"
        _make_plan_file(plans_dir)

        result = plan_to_todo(plans_dir, todo_dir)

        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert "Hook Debug Info" not in content

    def test_returns_none_when_plans_dir_missing(self, tmp_path):
        """Returns None when the plans directory does not exist."""
        plans_dir = tmp_path / "nonexistent"
        todo_dir = tmp_path / "todo"

        result = plan_to_todo(plans_dir, todo_dir)

        assert result is None


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


class TestContentHash:
    def test_content_hash_stable(self):
        """Same input always returns the same hash."""
        text = "# My Plan\n\nSome content."
        assert _content_hash(text) == _content_hash(text)

    def test_content_hash_empty_string(self):
        """Empty string returns the SHA-256 of an empty string without error."""
        import hashlib
        expected = hashlib.sha256(b"").hexdigest()
        assert _content_hash("") == expected

    def test_content_hash_different_inputs_differ(self):
        """Different inputs produce different hashes."""
        assert _content_hash("foo") != _content_hash("bar")


class TestPlanToTodoFromText:
    _PLAN = "# My Codex Plan\n\nThis is the plan body."

    def test_from_text_creates_todo(self, tmp_path):
        """Plan text with a heading creates a TODO file with correct frontmatter."""
        todo_dir = tmp_path / "todo"
        result = plan_to_todo_from_text(self._PLAN, todo_dir)

        assert result is not None
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "status: pending" in content
        assert "source: codex-plan" in content
        assert "source_hash:" in content
        assert "My Codex Plan" in content

    def test_from_text_empty_is_noop(self, tmp_path):
        """Empty text returns None and creates no file."""
        todo_dir = tmp_path / "todo"
        result = plan_to_todo_from_text("", todo_dir)
        assert result is None

    def test_from_text_whitespace_only_is_noop(self, tmp_path):
        """Whitespace-only text returns None."""
        todo_dir = tmp_path / "todo"
        result = plan_to_todo_from_text("   \n  ", todo_dir)
        assert result is None

    def test_from_text_dedup(self, tmp_path):
        """Calling twice with the same text returns None on the second call."""
        todo_dir = tmp_path / "todo"
        first = plan_to_todo_from_text(self._PLAN, todo_dir)
        assert first is not None

        second = plan_to_todo_from_text(self._PLAN, todo_dir)
        assert second is None

    def test_from_text_different_content_not_deduped(self, tmp_path):
        """Different text creates a second file (no false dedup)."""
        todo_dir = tmp_path / "todo"
        plan_a = "# Plan A\n\nContent A."
        plan_b = "# Plan B\n\nContent B."

        result_a = plan_to_todo_from_text(plan_a, todo_dir)
        result_b = plan_to_todo_from_text(plan_b, todo_dir)

        assert result_a is not None
        assert result_b is not None
        assert result_a != result_b

    def test_from_text_dedup_scans_in_progress(self, tmp_path):
        """Dedup also checks todo_dir/in-progress/ for duplicates."""
        todo_dir = tmp_path / "todo"
        in_progress = todo_dir / "in-progress"
        in_progress.mkdir(parents=True)

        # Manually place a file with the hash in in-progress
        h = _content_hash(self._PLAN.strip())
        existing = in_progress / "existing.md"
        existing.write_text(
            f"---\nstatus: in-progress\nsource: codex-plan\nsource_hash: {h}\n---\n\n{self._PLAN}\n",
            encoding="utf-8",
        )

        result = plan_to_todo_from_text(self._PLAN, todo_dir)
        assert result is None

    def test_from_text_no_heading_uses_untitled(self, tmp_path):
        """Text without a # heading produces a file named untitled-plan.md."""
        todo_dir = tmp_path / "todo"
        result = plan_to_todo_from_text("No heading here.", todo_dir)
        assert result is not None
        assert result.name.startswith("untitled-plan")

    def test_existing_plan_to_todo_unchanged(self, tmp_path):
        """Original plan_to_todo still works correctly after the module change."""
        plans_dir = tmp_path / "plans"
        _make_plan_file(plans_dir)
        todo_dir = tmp_path / "todo"

        result = plan_to_todo(plans_dir, todo_dir)
        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert "status: pending" in content
