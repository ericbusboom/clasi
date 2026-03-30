"""Tests for claude_agent_skills.hooks.role_guard module."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from claude_agent_skills.hooks.role_guard import main, SAFE_PREFIXES

_ROLE_GUARD_SCRIPT = str(
    Path(__file__).resolve().parents[2]
    / "claude_agent_skills"
    / "hooks"
    / "role_guard.py"
)


def _run_role_guard(
    tool_input: dict, cwd: str | None = None, env: dict | None = None,
) -> subprocess.CompletedProcess:
    """Run role_guard.py as a subprocess with the given tool input on stdin."""
    run_env = dict(os.environ)
    # Clear tier/name from parent env to avoid test pollution
    run_env.pop("CLASI_AGENT_TIER", None)
    run_env.pop("CLASI_AGENT_NAME", None)
    if env:
        run_env.update(env)
    return subprocess.run(
        [sys.executable, _ROLE_GUARD_SCRIPT],
        input=json.dumps(tool_input),
        capture_output=True,
        text=True,
        cwd=cwd,
        env=run_env,
    )


class TestRoleGuardBlocking:
    """Tests that role_guard blocks writes to non-safe paths."""

    def test_blocks_write_to_sprint_artifact(self, tmp_path):
        result = _run_role_guard(
            {"file_path": "docs/clasi/sprints/001/sprint.md"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 1
        assert "ROLE VIOLATION" in result.stdout

    def test_blocks_write_to_source_code(self, tmp_path):
        result = _run_role_guard(
            {"file_path": "claude_agent_skills/foo.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 1
        assert "ROLE VIOLATION" in result.stdout

    def test_block_message_suggests_subagents(self, tmp_path):
        result = _run_role_guard(
            {"file_path": "src/main.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 1
        assert "code-monkey" in result.stdout
        assert "sprint-planner" in result.stdout

    def test_blocks_write_to_tests(self, tmp_path):
        result = _run_role_guard(
            {"file_path": "tests/test_something.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 1


class TestRoleGuardSafeList:
    """Tests that role_guard allows writes to safe-listed paths."""

    def test_allows_write_to_claude_settings(self, tmp_path):
        result = _run_role_guard(
            {"file_path": ".claude/settings.json"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_allows_write_to_claude_md(self, tmp_path):
        result = _run_role_guard(
            {"file_path": "CLAUDE.md"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_allows_write_to_agents_md(self, tmp_path):
        result = _run_role_guard(
            {"file_path": "AGENTS.md"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_allows_write_to_claude_hooks(self, tmp_path):
        result = _run_role_guard(
            {"file_path": ".claude/hooks/role_guard.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0


class TestRoleGuardOOPBypass:
    """Tests that role_guard allows all writes when .clasi-oop flag exists."""

    def test_allows_write_when_oop_flag_exists(self, tmp_path):
        (tmp_path / ".clasi-oop").touch()
        result = _run_role_guard(
            {"file_path": "claude_agent_skills/foo.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_blocks_write_when_oop_flag_absent(self, tmp_path):
        result = _run_role_guard(
            {"file_path": "claude_agent_skills/foo.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 1


class TestRoleGuardRecoveryState:
    """Tests that role_guard allows writes when recovery state permits."""

    def test_allows_write_when_path_in_recovery_allowed_paths(self, tmp_path):
        # Set up a state DB with recovery state
        db_dir = tmp_path / "docs" / "clasi"
        db_dir.mkdir(parents=True)
        db_path = db_dir / ".clasi.db"

        from claude_agent_skills.state_db import write_recovery_state

        write_recovery_state(
            db_path=str(db_path),
            sprint_id="001",
            step="merge",
            allowed_paths=["docs/clasi/sprints/001/sprint.md"],
            reason="merge conflict",
        )

        result = _run_role_guard(
            {"file_path": "docs/clasi/sprints/001/sprint.md"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_blocks_write_when_path_not_in_recovery_allowed_paths(self, tmp_path):
        db_dir = tmp_path / "docs" / "clasi"
        db_dir.mkdir(parents=True)
        db_path = db_dir / ".clasi.db"

        from claude_agent_skills.state_db import write_recovery_state

        write_recovery_state(
            db_path=str(db_path),
            sprint_id="001",
            step="merge",
            allowed_paths=["docs/clasi/sprints/001/sprint.md"],
            reason="merge conflict",
        )

        result = _run_role_guard(
            {"file_path": "claude_agent_skills/foo.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 1

    def test_handles_missing_state_db_gracefully(self, tmp_path):
        # No DB exists -- should still block non-safe paths without crashing
        result = _run_role_guard(
            {"file_path": "claude_agent_skills/foo.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 1
        assert "ROLE VIOLATION" in result.stdout


class TestRoleGuardEdgeCases:
    """Tests for edge cases in role_guard."""

    def test_allows_when_no_file_path_in_input(self, tmp_path):
        result = _run_role_guard(
            {"content": "some content"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_extracts_path_from_path_key(self, tmp_path):
        result = _run_role_guard(
            {"path": "claude_agent_skills/foo.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 1

    def test_extracts_path_from_new_path_key(self, tmp_path):
        result = _run_role_guard(
            {"new_path": "claude_agent_skills/foo.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 1


class TestRoleGuardTierAware:
    """Tests that role_guard respects CLASI_AGENT_TIER."""

    def test_tier_2_allowed_to_write(self, tmp_path):
        """Task workers (tier 2) can write files — that's their job."""
        result = _run_role_guard(
            {"file_path": "guessing_game/menu.py"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "2", "CLASI_AGENT_NAME": "code-monkey"},
        )
        assert result.returncode == 0

    def test_tier_1_blocked_from_writing(self, tmp_path):
        """Domain controllers (tier 1) must dispatch, not write."""
        result = _run_role_guard(
            {"file_path": "guessing_game/menu.py"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "1", "CLASI_AGENT_NAME": "sprint-executor"},
        )
        assert result.returncode == 1
        assert "sprint-executor" in result.stdout
        assert "dispatch_to_code_monkey" in result.stdout

    def test_tier_0_blocked_from_writing(self, tmp_path):
        """Main controller (tier 0) must dispatch, not write."""
        result = _run_role_guard(
            {"file_path": "src/main.py"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "0", "CLASI_AGENT_NAME": "team-lead"},
        )
        assert result.returncode == 1
        assert "team-lead" in result.stdout

    def test_no_tier_defaults_to_blocked(self, tmp_path):
        """No tier set (interactive session) blocks like team-lead."""
        result = _run_role_guard(
            {"file_path": "src/main.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 1

    def test_tier_2_still_blocked_by_safe_list_only(self, tmp_path):
        """Tier 2 is allowed to write anything, not just safe list paths."""
        result = _run_role_guard(
            {"file_path": "docs/clasi/sprints/001/sprint.md"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "2", "CLASI_AGENT_NAME": "architect"},
        )
        assert result.returncode == 0

    def test_tier_1_error_message_suggests_dispatch_tools(self, tmp_path):
        """Tier 1 error message names dispatch_to_* tools, not agent names."""
        result = _run_role_guard(
            {"file_path": "guessing_game/game.py"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "1", "CLASI_AGENT_NAME": "sprint-executor"},
        )
        assert result.returncode == 1
        assert "dispatch_to_code_monkey" in result.stdout
        assert "dispatch_to_architect" in result.stdout
