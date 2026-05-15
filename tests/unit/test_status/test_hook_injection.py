"""Unit tests for hook-injection handlers: handle_status_inject and the
status block prepended by handle_subagent_start.

All tests use tmp_path to simulate different project states (no .clasi/,
.clasi/ without oop, .clasi/oop present) and capture stdout to verify the
emitted block.
"""

from __future__ import annotations

import os
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from clasi.hook_handlers import handle_status_inject, handle_subagent_start


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chdir(tmp_path: Path):
    """Context manager: change cwd to tmp_path and restore on exit."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            yield
        finally:
            os.chdir(old)

    return _ctx()


def _capture_stdout(fn, *args, **kwargs) -> tuple[str, int]:
    """Call fn(*args, **kwargs), capture stdout, return (output, exit_code).

    Catches SystemExit so the hook's sys.exit() doesn't kill the test.
    """
    buf = StringIO()
    exit_code = 0
    with patch("sys.stdout", buf):
        try:
            fn(*args, **kwargs)
        except SystemExit as exc:
            exit_code = int(exc.code) if exc.code is not None else 0
    return buf.getvalue(), exit_code


def _make_clasi_dir(tmp_path: Path) -> Path:
    """Create a minimal .clasi/ directory so project is CLASI-initialized."""
    clasi_dir = tmp_path / ".clasi"
    clasi_dir.mkdir()
    return clasi_dir


# ---------------------------------------------------------------------------
# Minimal status stub so tests don't need a real project on disk
# ---------------------------------------------------------------------------


def _minimal_status_dict() -> dict:
    return {
        "agent": "team-lead",
        "computed_at": "2026-01-01T00:00:00+00:00",
        "project": {"state": "active"},
        "sprints": [],
        "issues": [],
        "inconsistencies": [],
        "notes": {"current_focus": ""},
    }


# ---------------------------------------------------------------------------
# handle_status_inject — OOP bypass
# ---------------------------------------------------------------------------


class TestStatusInjectOopBypass:
    """handle_status_inject exits 0 with no output when .clasi/oop exists."""

    def test_oop_bypass_no_output(self, tmp_path):
        clasi_dir = _make_clasi_dir(tmp_path)
        (clasi_dir / "oop").touch()

        with _chdir(tmp_path):
            output, code = _capture_stdout(handle_status_inject, {})

        assert code == 0
        assert output == ""

    def test_oop_bypass_does_not_call_build_status(self, tmp_path):
        clasi_dir = _make_clasi_dir(tmp_path)
        (clasi_dir / "oop").touch()

        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block") as mock_build:
                try:
                    handle_status_inject({})
                except SystemExit:
                    pass

        mock_build.assert_not_called()


# ---------------------------------------------------------------------------
# handle_status_inject — non-CLASI project (no .clasi/ dir)
# ---------------------------------------------------------------------------


class TestStatusInjectNonClasi:
    """handle_status_inject exits 0 with no output when .clasi/ does not exist."""

    def test_no_clasi_dir_no_output(self, tmp_path):
        # tmp_path has no .clasi/ subdirectory
        with _chdir(tmp_path):
            output, code = _capture_stdout(handle_status_inject, {})

        assert code == 0
        assert output == ""

    def test_no_clasi_dir_does_not_call_build_status(self, tmp_path):
        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block") as mock_build:
                try:
                    handle_status_inject({})
                except SystemExit:
                    pass

        mock_build.assert_not_called()


# ---------------------------------------------------------------------------
# handle_status_inject — valid CLASI project
# ---------------------------------------------------------------------------


class TestStatusInjectValid:
    """handle_status_inject emits a ## CLASI status YAML block on a valid project."""

    def test_output_contains_heading(self, tmp_path):
        _make_clasi_dir(tmp_path)
        with _chdir(tmp_path):
            with patch(
                "clasi.hook_handlers._build_status_block",
                return_value="## CLASI status\n\n```yaml\nagent: team-lead\n```\n",
            ):
                output, code = _capture_stdout(handle_status_inject, {})

        assert code == 0
        assert "## CLASI status" in output

    def test_output_contains_yaml_fence(self, tmp_path):
        _make_clasi_dir(tmp_path)
        with _chdir(tmp_path):
            with patch(
                "clasi.hook_handlers._build_status_block",
                return_value="## CLASI status\n\n```yaml\nagent: team-lead\n```\n",
            ):
                output, code = _capture_stdout(handle_status_inject, {})

        assert "```yaml" in output
        assert "agent: team-lead" in output

    def test_uses_clasi_agent_name_env(self, tmp_path):
        _make_clasi_dir(tmp_path)
        captured_agent = {}

        def fake_build(agent: str) -> str:
            captured_agent["agent"] = agent
            return f"## CLASI status\n\n```yaml\nagent: {agent}\n```\n"

        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block", side_effect=fake_build):
                with patch.dict(os.environ, {"CLASI_AGENT_NAME": "programmer"}):
                    _capture_stdout(handle_status_inject, {})

        assert captured_agent["agent"] == "programmer"

    def test_defaults_to_team_lead_when_no_env(self, tmp_path):
        _make_clasi_dir(tmp_path)
        captured_agent = {}

        def fake_build(agent: str) -> str:
            captured_agent["agent"] = agent
            return f"## CLASI status\n\n```yaml\nagent: {agent}\n```\n"

        env_without_agent = {k: v for k, v in os.environ.items() if k != "CLASI_AGENT_NAME"}
        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block", side_effect=fake_build):
                with patch.dict(os.environ, env_without_agent, clear=True):
                    _capture_stdout(handle_status_inject, {})

        assert captured_agent["agent"] == "team-lead"

    def test_empty_block_no_output(self, tmp_path):
        """If _build_status_block returns empty string, no output is produced."""
        _make_clasi_dir(tmp_path)
        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block", return_value=""):
                output, code = _capture_stdout(handle_status_inject, {})

        assert code == 0
        assert output == ""


# ---------------------------------------------------------------------------
# handle_subagent_start — status block prepended
# ---------------------------------------------------------------------------


class TestSubagentStartStatusBlock:
    """handle_subagent_start prepends a ## CLASI status block to stdout."""

    def _minimal_payload(self, agent_type: str = "programmer") -> dict:
        return {
            "agent_type": agent_type,
            "agent_id": "agent-test-001",
            "session_id": "sess-001",
        }

    def test_status_block_prepended_for_programmer(self, tmp_path):
        _make_clasi_dir(tmp_path)
        with _chdir(tmp_path):
            with patch(
                "clasi.hook_handlers._build_status_block",
                return_value="## CLASI status\n\n```yaml\nagent: programmer\n```\n",
            ):
                output, _code = _capture_stdout(
                    handle_subagent_start, self._minimal_payload("programmer")
                )

        assert "## CLASI status" in output

    def test_agent_type_maps_to_programmer_role(self, tmp_path):
        _make_clasi_dir(tmp_path)
        captured_agent = {}

        def fake_build(agent: str) -> str:
            captured_agent["agent"] = agent
            return f"## CLASI status\n\n```yaml\nagent: {agent}\n```\n"

        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block", side_effect=fake_build):
                _capture_stdout(
                    handle_subagent_start, self._minimal_payload("programmer")
                )

        assert captured_agent["agent"] == "programmer"

    def test_agent_type_maps_to_sprint_planner_role(self, tmp_path):
        _make_clasi_dir(tmp_path)
        captured_agent = {}

        def fake_build(agent: str) -> str:
            captured_agent["agent"] = agent
            return f"## CLASI status\n\n```yaml\nagent: {agent}\n```\n"

        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block", side_effect=fake_build):
                _capture_stdout(
                    handle_subagent_start, self._minimal_payload("sprint-planner")
                )

        assert captured_agent["agent"] == "sprint-planner"

    def test_unknown_agent_type_defaults_to_team_lead(self, tmp_path):
        _make_clasi_dir(tmp_path)
        captured_agent = {}

        def fake_build(agent: str) -> str:
            captured_agent["agent"] = agent
            return f"## CLASI status\n\n```yaml\nagent: {agent}\n```\n"

        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block", side_effect=fake_build):
                _capture_stdout(
                    handle_subagent_start, self._minimal_payload("unknown-agent")
                )

        assert captured_agent["agent"] == "team-lead"

    def test_oop_suppresses_status_block(self, tmp_path):
        clasi_dir = _make_clasi_dir(tmp_path)
        (clasi_dir / "oop").touch()

        with _chdir(tmp_path):
            with patch(
                "clasi.hook_handlers._build_status_block",
            ) as mock_build:
                _capture_stdout(
                    handle_subagent_start, self._minimal_payload("programmer")
                )

        mock_build.assert_not_called()


# ---------------------------------------------------------------------------
# handle_hook dispatcher recognizes status-inject
# ---------------------------------------------------------------------------


class TestHookDispatch:
    """Verify handle_hook routes 'status-inject' correctly."""

    def test_status_inject_routed(self, tmp_path):
        from clasi.hook_handlers import handle_hook

        with _chdir(tmp_path):
            with patch("clasi.hook_handlers.handle_status_inject") as mock_handler:
                with patch("clasi.hook_handlers.read_payload", return_value={}):
                    mock_handler.side_effect = SystemExit(0)
                    try:
                        handle_hook("status-inject")
                    except SystemExit:
                        pass

        mock_handler.assert_called_once_with({})
