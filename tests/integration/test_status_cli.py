"""Integration tests for the ``clasi status`` CLI command.

All tests run against *this* repository's ``.clasi/`` directory so they
exercise the real reader, reporter, and narrowing stack end-to-end.  They
use :class:`click.testing.CliRunner` for subprocess isolation while keeping
the working directory anchored to the repo root so the command can find
``.clasi/``.

The tests verify:

- Help text is accessible.
- Default invocation (no flags) produces parseable YAML with the required
  top-level keys.
- ``--format json`` produces parseable JSON.
- ``--agent`` / ``--sprint`` / ``--ticket`` flags are accepted and produce
  narrowed output.
- Invocation from a non-CLASI directory exits non-zero with a helpful error.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from clasi.cli import cli

# Root of this repository (parent of tests/).
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestStatusHelp:
    def test_help_shows_flags(self) -> None:
        """``clasi status --help`` shows all four flags."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0
        assert "--agent" in result.output
        assert "--sprint" in result.output
        assert "--ticket" in result.output
        assert "--format" in result.output


class TestStatusDefaultOutput:
    """Default invocation (no flags) against this repo's .clasi/ directory."""

    def _invoke(self, extra_args: list[str] | None = None) -> "click.testing.Result":
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=REPO_ROOT):
            # Change into repo root so .clasi/ is visible.
            import os
            orig = os.getcwd()
            os.chdir(REPO_ROOT)
            try:
                return runner.invoke(cli, ["status"] + (extra_args or []))
            finally:
                os.chdir(orig)

    def test_exit_code_zero(self) -> None:
        result = self._invoke()
        assert result.exit_code == 0, f"stderr/output: {result.output}"

    def test_output_is_valid_yaml(self) -> None:
        result = self._invoke()
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert isinstance(parsed, dict)

    def test_required_top_level_keys_present(self) -> None:
        result = self._invoke()
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        required = {"agent", "computed_at", "project", "sprints", "issues", "notes", "inconsistencies"}
        assert required.issubset(parsed.keys()), (
            f"Missing keys: {required - set(parsed.keys())}"
        )

    def test_agent_defaults_to_team_lead(self) -> None:
        result = self._invoke()
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert parsed["agent"] == "team-lead"


class TestStatusJsonFormat:
    def test_json_output_parseable(self) -> None:
        runner = CliRunner()
        import os
        orig = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            result = runner.invoke(cli, ["status", "--format", "json"])
        finally:
            os.chdir(orig)

        assert result.exit_code == 0, f"output: {result.output}"
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)
        assert "agent" in parsed


class TestStatusAgentFlag:
    def test_agent_flag_overrides_default(self) -> None:
        runner = CliRunner()
        import os
        orig = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            result = runner.invoke(cli, ["status", "--agent", "sprint-planner"])
        finally:
            os.chdir(orig)

        assert result.exit_code == 0, f"output: {result.output}"
        parsed = yaml.safe_load(result.output)
        assert parsed["agent"] == "sprint-planner"

    def test_sprint_planner_sprint_flag(self) -> None:
        runner = CliRunner()
        import os
        orig = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            result = runner.invoke(
                cli, ["status", "--agent", "sprint-planner", "--sprint", "006"]
            )
        finally:
            os.chdir(orig)

        assert result.exit_code == 0, f"output: {result.output}"
        parsed = yaml.safe_load(result.output)
        assert isinstance(parsed, dict)

    def test_programmer_ticket_flag(self) -> None:
        runner = CliRunner()
        import os
        orig = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            result = runner.invoke(
                cli,
                ["status", "--agent", "programmer", "--ticket", "006-003"],
            )
        finally:
            os.chdir(orig)

        assert result.exit_code == 0, f"output: {result.output}"
        parsed = yaml.safe_load(result.output)
        assert isinstance(parsed, dict)


class TestStatusEnvVar:
    def test_clasi_agent_name_env_var(self) -> None:
        """$CLASI_AGENT_NAME is used when --agent is not supplied."""
        import os
        runner = CliRunner()
        orig = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            result = runner.invoke(
                cli, ["status"], env={"CLASI_AGENT_NAME": "sprint-planner"}
            )
        finally:
            os.chdir(orig)

        assert result.exit_code == 0, f"output: {result.output}"
        parsed = yaml.safe_load(result.output)
        assert parsed["agent"] == "sprint-planner"

    def test_agent_flag_wins_over_env_var(self) -> None:
        """Explicit --agent overrides $CLASI_AGENT_NAME."""
        import os
        runner = CliRunner()
        orig = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            result = runner.invoke(
                cli,
                ["status", "--agent", "team-lead"],
                env={"CLASI_AGENT_NAME": "sprint-planner"},
            )
        finally:
            os.chdir(orig)

        assert result.exit_code == 0, f"output: {result.output}"
        parsed = yaml.safe_load(result.output)
        assert parsed["agent"] == "team-lead"


class TestStatusNonClasiDirectory:
    def test_exits_nonzero_without_clasi_dir(self, tmp_path: Path) -> None:
        """Running from a directory without .clasi/ prints an error and exits non-zero."""
        import os
        runner = CliRunner()
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(cli, ["status"])
        finally:
            os.chdir(orig)

        assert result.exit_code != 0
        assert ".clasi/" in result.output or ".clasi" in result.output
