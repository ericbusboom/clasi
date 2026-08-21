"""Integration tests for the ``get_status`` MCP tool.

All tests call the tool function directly (not via HTTP/stdio) so they
exercise the real reader, reporter, and narrowing stack end-to-end while
running in-process.

The working directory is changed to the repo root so the tool can
discover ``.clasi/``.  The singleton project is reset before and after
each test to prevent cross-test contamination.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# 032/008: real reader/reporter/narrowing stack against this repo's real
# `.clasi/` directory -- measured at 10-14s per test (032/008 durations
# audit), real-fs/real-git tier by both duration and kind.
pytestmark = [pytest.mark.slow]

# Root of this repository (two directories above tests/).
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Required top-level keys present in a team-lead full status response.
REQUIRED_TOP_LEVEL_KEYS = {
    "agent",
    "computed_at",
    "project",
    "sprints",
    "issues",
    "notes",
    "inconsistencies",
}


@pytest.fixture(autouse=True)
def in_repo_root(monkeypatch, tmp_path):
    """Change cwd to repo root and reset the singleton project for each test."""
    from clasi.mcp_server import set_project, reset_project

    monkeypatch.chdir(REPO_ROOT)
    set_project(REPO_ROOT)
    yield
    reset_project()


class TestGetStatusDefaultCall:
    """Default invocation: no arguments → team-lead scoped full status."""

    def test_returns_valid_json(self) -> None:
        from clasi.tools.process_tools import get_status

        result = get_status()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_required_top_level_keys_present(self) -> None:
        from clasi.tools.process_tools import get_status

        parsed = json.loads(get_status())
        assert REQUIRED_TOP_LEVEL_KEYS.issubset(parsed.keys()), (
            f"Missing keys: {REQUIRED_TOP_LEVEL_KEYS - set(parsed.keys())}"
        )

    def test_agent_defaults_to_team_lead(self) -> None:
        from clasi.tools.process_tools import get_status

        parsed = json.loads(get_status())
        assert parsed["agent"] == "team-lead"

    def test_no_error_key_in_success_response(self) -> None:
        from clasi.tools.process_tools import get_status

        parsed = json.loads(get_status())
        assert "error" not in parsed


class TestGetStatusAgentScoping:
    """Narrowing: sprint-planner and programmer views."""

    def test_sprint_planner_with_sprint_id(self) -> None:
        from clasi.tools.process_tools import get_status

        result = get_status(agent="sprint-planner", sprint_id="006")
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert "error" not in parsed
        assert parsed.get("agent") == "sprint-planner"

    def test_programmer_with_ticket_id(self) -> None:
        from clasi.tools.process_tools import get_status

        result = get_status(agent="programmer", ticket_id="006-003")
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert "error" not in parsed
        assert parsed.get("agent") == "programmer"


class TestGetStatusEnvVar:
    """$CLASI_AGENT_NAME is used when ``agent`` is not overridden."""

    def test_env_var_sets_agent(self, monkeypatch) -> None:
        from clasi.tools.process_tools import get_status

        monkeypatch.setenv("CLASI_AGENT_NAME", "sprint-planner")
        # Pass the empty string to simulate "not supplied" — the tool
        # falls back to the env var in that case.
        result = get_status(agent="")
        parsed = json.loads(result)
        assert parsed.get("agent") == "sprint-planner"

    def test_explicit_agent_wins_over_env_var(self, monkeypatch) -> None:
        from clasi.tools.process_tools import get_status

        monkeypatch.setenv("CLASI_AGENT_NAME", "sprint-planner")
        result = get_status(agent="team-lead")
        parsed = json.loads(result)
        assert parsed.get("agent") == "team-lead"


class TestGetStatusNonClasiProject:
    """Returns an error JSON object when the directory is not CLASI-initialized."""

    def test_error_object_returned(self, tmp_path, monkeypatch) -> None:
        from clasi.mcp_server import set_project
        from clasi.tools.process_tools import get_status

        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)

        result = get_status()
        parsed = json.loads(result)
        assert "error" in parsed
        assert parsed["error"] == "not a CLASI project"
