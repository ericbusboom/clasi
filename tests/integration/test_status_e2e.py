"""End-to-end integration tests for the ``clasi status`` feature (ticket 006-008).

Exercises all eight verification items from the source issue
``clasi-status-per-agent-process-status-with-gate-derived-next-step-notes.md``:

1. ``clasi status`` prints YAML matching the documented output shape.
2. ``clasi status --format json`` parses as valid JSON with the same shape.
3. ``clasi status --agent sprint-planner --sprint 006`` narrows correctly.
4. ``clasi status --agent programmer --ticket 006-001`` narrows to one ticket.
5. MCP ``get_status()`` returns the JSON form of the same data.
6. MCP ``get_status(agent="sprint-planner", sprint_id="006")`` returns narrowed JSON.
7. A sprint with ``status: planned`` while ``is_architecture_present`` is False
   produces an ``inconsistencies:`` entry of kind ``state_drift``.
8. A non-CLASI directory / ``.clasi/oop`` case is silent.

All live tests run against *this* repository's ``.clasi/`` directory so they
exercise the full stack (reader → reporter → narrowing → formatting) on real
data.  Synthetic-fixture tests use ``tmp_path`` for isolation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from clasi.cli import cli

# Root of this repository (two levels up from this file).
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Required top-level keys present in any well-formed status response.
REQUIRED_KEYS = {
    "agent",
    "computed_at",
    "project",
    "sprints",
    "issues",
    "notes",
    "inconsistencies",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invoke_status(*extra_args: str) -> "click.testing.Result":
    """Run ``clasi status [extra_args]`` from the repo root and return the result."""
    runner = CliRunner()
    orig = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        return runner.invoke(cli, ["status"] + list(extra_args))
    finally:
        os.chdir(orig)


# ---------------------------------------------------------------------------
# Verification 1: YAML output shape
# ---------------------------------------------------------------------------


class TestYamlOutputShape:
    """V1: ``clasi status`` prints YAML matching the documented output shape."""

    def test_exit_code_zero(self) -> None:
        result = _invoke_status()
        assert result.exit_code == 0, f"output: {result.output}"

    def test_output_is_valid_yaml(self) -> None:
        result = _invoke_status()
        parsed = yaml.safe_load(result.output)
        assert isinstance(parsed, dict), "Expected a YAML dict at top level"

    def test_all_required_top_level_keys_present(self) -> None:
        result = _invoke_status()
        parsed = yaml.safe_load(result.output)
        missing = REQUIRED_KEYS - set(parsed.keys())
        assert not missing, f"Missing top-level keys: {missing}"

    def test_project_block_has_state_and_transitions(self) -> None:
        result = _invoke_status()
        parsed = yaml.safe_load(result.output)
        project = parsed["project"]
        assert "state" in project
        assert "available_transitions" in project

    def test_sprints_is_list(self) -> None:
        result = _invoke_status()
        parsed = yaml.safe_load(result.output)
        assert isinstance(parsed["sprints"], list)

    def test_issues_has_total_pending_assigned(self) -> None:
        result = _invoke_status()
        parsed = yaml.safe_load(result.output)
        issues = parsed["issues"]
        assert "total" in issues
        assert "pending" in issues
        assert "assigned_to_sprint" in issues

    def test_notes_has_current_focus_and_actions(self) -> None:
        result = _invoke_status()
        parsed = yaml.safe_load(result.output)
        notes = parsed["notes"]
        assert "current_focus" in notes
        assert "allowed_next_actions" in notes
        assert "blocked_actions" in notes

    def test_inconsistencies_is_list(self) -> None:
        result = _invoke_status()
        parsed = yaml.safe_load(result.output)
        assert isinstance(parsed["inconsistencies"], list)

    def test_agent_defaults_to_team_lead(self) -> None:
        result = _invoke_status()
        parsed = yaml.safe_load(result.output)
        assert parsed["agent"] == "team-lead"

    def test_sprint_entries_have_id_state_tickets(self) -> None:
        """Every sprint entry has id, state, and tickets keys."""
        result = _invoke_status()
        parsed = yaml.safe_load(result.output)
        for sprint in parsed["sprints"]:
            assert "id" in sprint, f"Sprint entry missing 'id': {sprint}"
            assert "state" in sprint, f"Sprint entry missing 'state': {sprint}"
            assert "tickets" in sprint, f"Sprint entry missing 'tickets': {sprint}"


# ---------------------------------------------------------------------------
# Verification 2: JSON format
# ---------------------------------------------------------------------------


class TestJsonFormat:
    """V2: ``clasi status --format json`` parses as valid JSON with the same shape."""

    def test_exit_code_zero(self) -> None:
        result = _invoke_status("--format", "json")
        assert result.exit_code == 0, f"output: {result.output}"

    def test_output_is_valid_json(self) -> None:
        result = _invoke_status("--format", "json")
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)

    def test_all_required_keys_present(self) -> None:
        result = _invoke_status("--format", "json")
        parsed = json.loads(result.output)
        missing = REQUIRED_KEYS - set(parsed.keys())
        assert not missing, f"Missing keys: {missing}"

    def test_json_agent_is_team_lead(self) -> None:
        result = _invoke_status("--format", "json")
        parsed = json.loads(result.output)
        assert parsed["agent"] == "team-lead"

    def test_json_project_has_state(self) -> None:
        result = _invoke_status("--format", "json")
        parsed = json.loads(result.output)
        assert "state" in parsed["project"]


# ---------------------------------------------------------------------------
# Verification 3: sprint-planner narrowing
# ---------------------------------------------------------------------------


class TestSprintPlannerNarrowing:
    """V3: ``--agent sprint-planner --sprint 006`` narrows to sprint 006."""

    def test_exit_code_zero(self) -> None:
        result = _invoke_status("--agent", "sprint-planner", "--sprint", "006")
        assert result.exit_code == 0, f"output: {result.output}"

    def test_agent_field_is_sprint_planner(self) -> None:
        result = _invoke_status("--agent", "sprint-planner", "--sprint", "006")
        parsed = yaml.safe_load(result.output)
        assert parsed["agent"] == "sprint-planner"

    def test_only_sprint_006_present(self) -> None:
        result = _invoke_status("--agent", "sprint-planner", "--sprint", "006")
        parsed = yaml.safe_load(result.output)
        sprint_ids = [s["id"] for s in parsed["sprints"]]
        assert sprint_ids == ["006"], f"Expected only sprint 006, got {sprint_ids}"

    def test_no_ticket_details_in_sprint_entry(self) -> None:
        """Sprint-planner view should not include per-ticket detail entries."""
        result = _invoke_status("--agent", "sprint-planner", "--sprint", "006")
        parsed = yaml.safe_load(result.output)
        for sprint in parsed["sprints"]:
            tickets = sprint.get("tickets", {})
            assert "details" not in tickets, (
                "sprint-planner view must not expose ticket details"
            )

    def test_project_block_preserved(self) -> None:
        result = _invoke_status("--agent", "sprint-planner", "--sprint", "006")
        parsed = yaml.safe_load(result.output)
        assert "project" in parsed
        assert "state" in parsed["project"]

    def test_notes_block_present_with_standard_keys(self) -> None:
        result = _invoke_status("--agent", "sprint-planner", "--sprint", "006")
        parsed = yaml.safe_load(result.output)
        notes = parsed["notes"]
        assert "current_focus" in notes
        assert "allowed_next_actions" in notes
        assert "blocked_actions" in notes


# ---------------------------------------------------------------------------
# Verification 4: programmer narrowing with ticket ID
# ---------------------------------------------------------------------------


class TestProgrammerNarrowing:
    """V4: ``--agent programmer --ticket 006-001`` narrows to one ticket."""

    def test_exit_code_zero(self) -> None:
        result = _invoke_status("--agent", "programmer", "--ticket", "006-001")
        assert result.exit_code == 0, f"output: {result.output}"

    def test_agent_field_is_programmer(self) -> None:
        result = _invoke_status("--agent", "programmer", "--ticket", "006-001")
        parsed = yaml.safe_load(result.output)
        assert parsed["agent"] == "programmer"

    def test_only_parent_sprint_present(self) -> None:
        result = _invoke_status("--agent", "programmer", "--ticket", "006-001")
        parsed = yaml.safe_load(result.output)
        assert len(parsed["sprints"]) == 1
        assert parsed["sprints"][0]["id"] == "006"

    def test_parent_sprint_has_id_and_state_only(self) -> None:
        """Programmer view of a sprint is summary only (id + state + tickets)."""
        result = _invoke_status("--agent", "programmer", "--ticket", "006-001")
        parsed = yaml.safe_load(result.output)
        sprint = parsed["sprints"][0]
        assert "id" in sprint
        assert "state" in sprint
        assert "available_transitions" not in sprint

    def test_ticket_detail_present_for_target_ticket(self) -> None:
        result = _invoke_status("--agent", "programmer", "--ticket", "006-001")
        parsed = yaml.safe_load(result.output)
        sprint = parsed["sprints"][0]
        details = sprint.get("tickets", {}).get("details", [])
        assert len(details) == 1, f"Expected exactly one ticket detail, got {len(details)}"
        # The detail's id may be stored as bare "001" or full "006-001"
        detail_id = str(details[0]["id"])
        assert detail_id in ("001", "006-001"), f"Unexpected ticket id: {detail_id!r}"

    def test_notes_focus_mentions_ticket_id(self) -> None:
        result = _invoke_status("--agent", "programmer", "--ticket", "006-001")
        parsed = yaml.safe_load(result.output)
        focus = parsed["notes"]["current_focus"]
        assert "006-001" in focus, (
            f"Expected ticket id '006-001' in current_focus, got: {focus!r}"
        )

    def test_project_block_present(self) -> None:
        result = _invoke_status("--agent", "programmer", "--ticket", "006-001")
        parsed = yaml.safe_load(result.output)
        assert "project" in parsed
        assert "state" in parsed["project"]


# ---------------------------------------------------------------------------
# Verification 5: MCP get_status default
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def in_repo_root(monkeypatch):
    """Change cwd to repo root and reset the singleton project."""
    from clasi.mcp_server import set_project, reset_project

    monkeypatch.chdir(REPO_ROOT)
    set_project(REPO_ROOT)
    yield
    reset_project()


class TestMcpGetStatusDefault:
    """V5: MCP ``get_status()`` returns JSON with the same shape."""

    @pytest.fixture(autouse=True)
    def _setup(self, in_repo_root):
        pass

    def test_returns_valid_json(self) -> None:
        from clasi.tools.process_tools import get_status

        result = get_status()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_required_keys_present(self) -> None:
        from clasi.tools.process_tools import get_status

        parsed = json.loads(get_status())
        missing = REQUIRED_KEYS - set(parsed.keys())
        assert not missing, f"Missing keys: {missing}"

    def test_agent_defaults_to_team_lead(self) -> None:
        from clasi.tools.process_tools import get_status

        parsed = json.loads(get_status())
        assert parsed["agent"] == "team-lead"

    def test_no_error_key_on_success(self) -> None:
        from clasi.tools.process_tools import get_status

        parsed = json.loads(get_status())
        assert "error" not in parsed


# ---------------------------------------------------------------------------
# Verification 6: MCP get_status with sprint-planner narrowing
# ---------------------------------------------------------------------------


class TestMcpGetStatusNarrowed:
    """V6: MCP ``get_status(agent="sprint-planner", sprint_id="006")`` narrows."""

    @pytest.fixture(autouse=True)
    def _setup(self, in_repo_root):
        pass

    def test_sprint_planner_sprint_id_returns_narrowed_json(self) -> None:
        from clasi.tools.process_tools import get_status

        result = get_status(agent="sprint-planner", sprint_id="006")
        parsed = json.loads(result)
        assert parsed.get("agent") == "sprint-planner"
        sprint_ids = [s["id"] for s in parsed.get("sprints", [])]
        assert sprint_ids == ["006"]

    def test_programmer_ticket_id_returns_narrowed_json(self) -> None:
        from clasi.tools.process_tools import get_status

        result = get_status(agent="programmer", ticket_id="006-001")
        parsed = json.loads(result)
        assert parsed.get("agent") == "programmer"
        assert len(parsed.get("sprints", [])) == 1


# ---------------------------------------------------------------------------
# Verification 7: Inconsistency detection — state_drift
# ---------------------------------------------------------------------------


class TestInconsistencyDetection:
    """V7: A sprint with status=planned while arch is absent produces state_drift."""

    def test_state_drift_entry_produced(self, tmp_path: Path) -> None:
        """Synthetic sprint: frontmatter status=planned but no architecture file."""
        from clasi.project import Project
        from clasi.status import build_status

        # Build a minimal .clasi/ layout
        clasi_dir = tmp_path / ".clasi"
        clasi_dir.mkdir()

        # Write legacy paths pin so Project resolves sprints_dir to .clasi/sprints
        (clasi_dir / "config.yaml").write_text(
            "process: se\npaths:\n  sprints: .clasi/sprints\n",
            encoding="utf-8",
        )

        # Write a minimal state DB so sprint lookup works
        sprints_dir = clasi_dir / "sprints" / "099-test-sprint"
        sprints_dir.mkdir(parents=True)
        tickets_dir = sprints_dir / "tickets"
        tickets_dir.mkdir()

        # Sprint.md declares status=planned but there is no architecture file
        sprint_md = sprints_dir / "sprint.md"
        sprint_md.write_text(
            "---\n"
            "id: '099'\n"
            "status: planned\n"
            "branch: sprint/099-test-sprint\n"
            "---\n\n# Test Sprint\n",
            encoding="utf-8",
        )

        project = Project(tmp_path)

        status = build_status(project, agent="team-lead")
        inconsistencies = status.get("inconsistencies", [])

        # Filter to sprint-level drift for sprint 099
        sprint_drift = [
            e for e in inconsistencies
            if e.get("machine") == "sprint" and e.get("id") == "099"
        ]
        assert len(sprint_drift) >= 1, (
            f"Expected at least one sprint state_drift for sprint 099; "
            f"got inconsistencies: {inconsistencies}"
        )
        entry = sprint_drift[0]
        assert entry["kind"] == "state_drift"
        assert entry["declared"] == "planned"
        assert "computed" in entry
        assert entry["computed"] != "planned"
        assert "explanation" in entry

    def test_state_drift_entry_has_required_fields(self, tmp_path: Path) -> None:
        """Each state_drift entry has: kind, machine, id, declared, computed, explanation."""
        from clasi.project import Project
        from clasi.status import build_status

        clasi_dir = tmp_path / ".clasi"
        clasi_dir.mkdir()

        # Write legacy paths pin so Project resolves sprints_dir to .clasi/sprints
        (clasi_dir / "config.yaml").write_text(
            "process: se\npaths:\n  sprints: .clasi/sprints\n",
            encoding="utf-8",
        )

        sprints_dir = clasi_dir / "sprints" / "098-test-sprint"
        sprints_dir.mkdir(parents=True)
        tickets_dir = sprints_dir / "tickets"
        tickets_dir.mkdir()

        sprint_md = sprints_dir / "sprint.md"
        sprint_md.write_text(
            "---\n"
            "id: '098'\n"
            "status: planned\n"
            "branch: sprint/098-test-sprint\n"
            "---\n\n# Test Sprint 098\n",
            encoding="utf-8",
        )

        project = Project(tmp_path)
        status = build_status(project, agent="team-lead")
        inconsistencies = status.get("inconsistencies", [])

        for entry in inconsistencies:
            required_fields = {"kind", "machine", "id", "declared", "computed", "explanation"}
            missing = required_fields - set(entry.keys())
            assert not missing, f"State drift entry missing fields {missing}: {entry}"


# ---------------------------------------------------------------------------
# Verification 8: Non-CLASI project / .clasi/oop silence
# ---------------------------------------------------------------------------


class TestNonClasiAndOopSilence:
    """V8: Non-CLASI project and .clasi/oop cases are handled correctly."""

    def test_non_clasi_directory_exits_nonzero(self, tmp_path: Path) -> None:
        """CLI exits non-zero with an error message in a non-CLASI directory."""
        runner = CliRunner()
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(cli, ["status"])
        finally:
            os.chdir(orig)
        assert result.exit_code != 0
        assert ".clasi" in result.output.lower() or "clasi" in result.output.lower()

    def test_hook_oop_file_suppresses_output(self, tmp_path: Path) -> None:
        """handle_status_inject is silent when .clasi/oop exists."""
        import sys
        from io import StringIO
        from unittest.mock import patch

        from clasi.hook_handlers import handle_status_inject

        clasi_dir = tmp_path / ".clasi"
        clasi_dir.mkdir()
        (clasi_dir / "oop").touch()

        buf = StringIO()
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch("sys.stdout", buf):
                try:
                    handle_status_inject({})
                except SystemExit:
                    pass
        finally:
            os.chdir(orig)

        assert buf.getvalue() == "", "Expected no output when .clasi/oop is present"

    def test_hook_no_clasi_dir_suppresses_output(self, tmp_path: Path) -> None:
        """handle_status_inject is silent when .clasi/ does not exist."""
        import sys
        from io import StringIO
        from unittest.mock import patch

        from clasi.hook_handlers import handle_status_inject

        # tmp_path has no .clasi/ directory
        buf = StringIO()
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch("sys.stdout", buf):
                try:
                    handle_status_inject({})
                except SystemExit:
                    pass
        finally:
            os.chdir(orig)

        assert buf.getvalue() == "", "Expected no output when .clasi/ is absent"

    def test_mcp_non_clasi_returns_error_json(self, tmp_path: Path, monkeypatch) -> None:
        """MCP get_status returns {error: ...} for non-CLASI directories."""
        from clasi.mcp_server import set_project, reset_project
        from clasi.tools.process_tools import get_status

        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        try:
            result = json.loads(get_status())
            assert "error" in result
        finally:
            reset_project()


# ---------------------------------------------------------------------------
# Bonus: Hook injection smoke-test with a real CLASI project
# ---------------------------------------------------------------------------


class TestHookInjectionSmoke:
    """Smoke-test the hook handler directly with a synthetic CLASI project."""

    def test_valid_project_emits_status_heading(self, tmp_path: Path) -> None:
        """handle_status_inject emits a ## CLASI status block for a real-looking project."""
        import sys
        from io import StringIO
        from unittest.mock import patch

        from clasi.hook_handlers import handle_status_inject

        clasi_dir = tmp_path / ".clasi"
        clasi_dir.mkdir()
        # Patch _build_status_block so we don't need a fully populated project
        with patch(
            "clasi.hook_handlers._build_status_block",
            return_value="## CLASI status\n\n```yaml\nagent: team-lead\n```\n",
        ):
            buf = StringIO()
            orig = os.getcwd()
            os.chdir(tmp_path)
            try:
                with patch("sys.stdout", buf):
                    try:
                        handle_status_inject({})
                    except SystemExit:
                        pass
            finally:
                os.chdir(orig)

        output = buf.getvalue()
        assert "## CLASI status" in output
        assert "```yaml" in output
        assert "agent: team-lead" in output
