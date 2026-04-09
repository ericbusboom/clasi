"""Tests for clasi.hooks.role_guard module."""

import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

_ROLE_GUARD_SCRIPT = str(
    Path(__file__).resolve().parents[2]
    / "clasi"
    / "plugin"
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

    def test_allows_team_lead_write_to_clasi_docs(self, tmp_path):
        """Team-lead (tier 0/unset) can write to docs/clasi/ non-sprint paths."""
        result = _run_role_guard(
            {"file_path": "docs/clasi/todo/my-todo.md"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_blocks_write_to_source_code(self, tmp_path):
        result = _run_role_guard(
            {"file_path": "clasi/foo.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2
        assert "ROLE VIOLATION" in result.stderr

    def test_block_message_suggests_subagents(self, tmp_path):
        result = _run_role_guard(
            {"file_path": "src/main.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2
        assert "programmer" in result.stderr
        assert "sprint-planner" in result.stderr

    def test_blocks_write_to_tests(self, tmp_path):
        result = _run_role_guard(
            {"file_path": "tests/test_something.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2


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
            {"file_path": "clasi/foo.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_blocks_write_when_oop_flag_absent(self, tmp_path):
        result = _run_role_guard(
            {"file_path": "clasi/foo.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2


class TestRoleGuardRecoveryState:
    """Tests that role_guard allows writes when recovery state permits."""

    def test_allows_write_when_path_in_recovery_allowed_paths(self, tmp_path):
        # Set up a state DB with recovery state
        db_dir = tmp_path / "docs" / "clasi"
        db_dir.mkdir(parents=True)
        db_path = db_dir / ".clasi.db"

        from clasi.state_db import write_recovery_state

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

        from clasi.state_db import write_recovery_state

        write_recovery_state(
            db_path=str(db_path),
            sprint_id="001",
            step="merge",
            allowed_paths=["docs/clasi/sprints/001/sprint.md"],
            reason="merge conflict",
        )

        result = _run_role_guard(
            {"file_path": "clasi/foo.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2

    def test_handles_missing_state_db_gracefully(self, tmp_path):
        # No DB exists -- should still block non-safe paths without crashing
        result = _run_role_guard(
            {"file_path": "clasi/foo.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2
        assert "ROLE VIOLATION" in result.stderr


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
            {"path": "clasi/foo.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2

    def test_extracts_path_from_new_path_key(self, tmp_path):
        result = _run_role_guard(
            {"new_path": "clasi/foo.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2


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
        assert result.returncode == 2
        assert "sprint-executor" in result.stderr
        assert "programmer" in result.stderr

    def test_tier_0_blocked_from_writing(self, tmp_path):
        """Main controller (tier 0) must dispatch, not write."""
        result = _run_role_guard(
            {"file_path": "src/main.py"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "0", "CLASI_AGENT_NAME": "team-lead"},
        )
        assert result.returncode == 2
        assert "team-lead" in result.stderr

    def test_no_tier_defaults_to_blocked(self, tmp_path):
        """No tier set (interactive session) blocks like team-lead."""
        result = _run_role_guard(
            {"file_path": "src/main.py"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2

    def test_tier_2_still_blocked_by_safe_list_only(self, tmp_path):
        """Tier 2 is allowed to write anything, not just safe list paths."""
        result = _run_role_guard(
            {"file_path": "docs/clasi/sprints/001/sprint.md"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "2", "CLASI_AGENT_NAME": "architect"},
        )
        assert result.returncode == 0

    def test_tier_1_error_message_suggests_agents(self, tmp_path):
        """Tier 1 error message names agent names."""
        result = _run_role_guard(
            {"file_path": "guessing_game/game.py"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "1", "CLASI_AGENT_NAME": "sprint-executor"},
        )
        assert result.returncode == 2
        assert "programmer" in result.stderr


class TestRoleGuardTeamLeadSprintBlock:
    """Tests that team-lead cannot directly edit sprint artifacts."""

    def test_tier_0_blocked_from_sprint_md(self, tmp_path):
        """Tier 0 cannot directly edit a sprint.md file."""
        result = _run_role_guard(
            {"file_path": "docs/clasi/sprints/001/sprint.md"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "0"},
        )
        assert result.returncode == 2
        assert "ROLE VIOLATION" in result.stderr

    def test_tier_0_blocked_from_sprint_ticket(self, tmp_path):
        """Tier 0 cannot directly edit a ticket file under sprints/."""
        result = _run_role_guard(
            {"file_path": "docs/clasi/sprints/001/tickets/001-foo.md"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "0"},
        )
        assert result.returncode == 2
        assert "ROLE VIOLATION" in result.stderr

    def test_tier_0_still_allowed_for_todo(self, tmp_path):
        """Tier 0 can write to docs/clasi/todo/."""
        result = _run_role_guard(
            {"file_path": "docs/clasi/todo/my-todo.md"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "0"},
        )
        assert result.returncode == 0

    def test_tier_0_still_allowed_for_reflections(self, tmp_path):
        """Tier 0 can write to docs/clasi/reflections/."""
        result = _run_role_guard(
            {"file_path": "docs/clasi/reflections/2026-04-01-foo.md"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "0"},
        )
        assert result.returncode == 0

    def test_tier_1_allowed_for_sprint_md(self, tmp_path):
        """Sprint-planner (tier 1) can write to sprint artifacts."""
        result = _run_role_guard(
            {"file_path": "docs/clasi/sprints/001/sprint.md"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "1"},
        )
        assert result.returncode == 0

    def test_tier_2_allowed_for_sprint_md(self, tmp_path):
        """Programmer (tier 2) can write to sprint artifacts."""
        result = _run_role_guard(
            {"file_path": "docs/clasi/sprints/001/sprint.md"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "2"},
        )
        assert result.returncode == 0

    def test_oop_bypass_allows_tier_0_sprint_write(self, tmp_path):
        """OOP flag bypasses sprint block for tier 0."""
        (tmp_path / ".clasi-oop").touch()
        result = _run_role_guard(
            {"file_path": "docs/clasi/sprints/001/sprint.md"},
            cwd=str(tmp_path),
            env={"CLASI_AGENT_TIER": "0"},
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Direct unit tests — call handle_role_guard() without subprocess
# ---------------------------------------------------------------------------


class TestRoleGuardDirect:
    """Direct unit tests for handle_role_guard().

    These call the function directly (not via subprocess) to exercise the
    logic without spawning a child process. We:
      - chdir to a tmp_path with no DB and no .clasi-oop file
      - patch _log_hook_event to suppress log file I/O
      - patch os.environ to control CLASI_AGENT_TIER
      - assert SystemExit.code for each scenario
    """

    def _call(self, payload, env_overrides=None, monkeypatch=None, tmp_path=None):
        """Call handle_role_guard with controlled env and cwd."""
        from clasi.hook_handlers import handle_role_guard
        from unittest.mock import patch

        # Build a clean env: strip tier/name from the real env
        clean_env = dict(os.environ)
        clean_env.pop("CLASI_AGENT_TIER", None)
        clean_env.pop("CLASI_AGENT_NAME", None)
        if env_overrides:
            clean_env.update(env_overrides)

        with patch.dict(os.environ, clean_env, clear=True), \
             patch("clasi.hook_handlers._log_hook_event"), \
             patch("os.getcwd", return_value=str(tmp_path)):
            # Patch Path(".clasi-oop").exists() and Path("docs/clasi/.clasi.db").exists()
            # by running in tmp_path so relative Path objects resolve there
            old_cwd = os.getcwd()
            os.chdir(tmp_path)
            try:
                with pytest.raises(SystemExit) as exc_info:
                    handle_role_guard(payload)
            finally:
                os.chdir(old_cwd)
        return exc_info.value.code

    def test_role_guard_blocks_source_file_tier0(self, tmp_path):
        """tier-0 (env unset, no DB) writing clasi/cli.py must be blocked (exit 2)."""
        code = self._call({"file_path": "clasi/cli.py"}, tmp_path=tmp_path)
        assert code == 2

    def test_role_guard_blocks_toml_tier0(self, tmp_path):
        """tier-0 writing pyproject.toml must be blocked (exit 2)."""
        code = self._call({"file_path": "pyproject.toml"}, tmp_path=tmp_path)
        assert code == 2

    def test_role_guard_allows_docs_clasi_tier0(self, tmp_path):
        """tier-0 writing to docs/clasi/todo/ is allowed (exit 0)."""
        code = self._call({"file_path": "docs/clasi/todo/x.md"}, tmp_path=tmp_path)
        assert code == 0

    def test_role_guard_blocks_docs_clasi_sprints_tier0(self, tmp_path):
        """tier-0 writing to docs/clasi/sprints/ must be blocked (exit 2)."""
        code = self._call(
            {"file_path": "docs/clasi/sprints/001/sprint.md"}, tmp_path=tmp_path
        )
        assert code == 2

    def test_role_guard_allows_claude_settings_tier0(self, tmp_path):
        """tier-0 writing to .claude/settings.json is allowed (exit 0)."""
        code = self._call({"file_path": ".claude/settings.json"}, tmp_path=tmp_path)
        assert code == 0

    def test_role_guard_allows_claude_md_tier0(self, tmp_path):
        """tier-0 writing to CLAUDE.md is allowed (exit 0)."""
        code = self._call({"file_path": "CLAUDE.md"}, tmp_path=tmp_path)
        assert code == 0

    def test_role_guard_allows_tier2_source_file(self, tmp_path):
        """tier-2 (programmer) writing clasi/cli.py is allowed (exit 0)."""
        code = self._call(
            {"file_path": "clasi/cli.py"},
            env_overrides={"CLASI_AGENT_TIER": "2"},
            tmp_path=tmp_path,
        )
        assert code == 0

    def test_role_guard_oop_bypass(self, tmp_path):
        """When .clasi-oop exists, any path is allowed (exit 0)."""
        (tmp_path / ".clasi-oop").touch()
        code = self._call({"file_path": "clasi/cli.py"}, tmp_path=tmp_path)
        assert code == 0
