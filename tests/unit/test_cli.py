"""Tests for the CLASI CLI entry point."""

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from clasi.cli import cli


class TestCliGroup:
    def test_help_shows_description(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "CLASI" in result.output

    def test_version_flag(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output


class TestInitCommand:
    def test_init_creates_files(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0
        # Should create /se skill from plugin
        assert (tmp_path / ".claude" / "skills" / "se" / "SKILL.md").is_file()
        # Should create MCP config
        assert (tmp_path / ".mcp.json").is_file()

    def test_init_default_target_uses_cwd(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0
            assert Path(".mcp.json").is_file()

    def test_init_nonexistent_target_fails(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "/nonexistent/path/xyz"])
        assert result.exit_code != 0

    def test_init_is_idempotent(self, tmp_path):
        runner = CliRunner()
        result1 = runner.invoke(cli, ["init", str(tmp_path)])
        assert result1.exit_code == 0
        result2 = runner.invoke(cli, ["init", str(tmp_path)])
        assert result2.exit_code == 0


class TestMcpCommand:
    def test_mcp_calls_run_server(self):
        with patch(
            "clasi.mcp_server.run_server",
        ) as mock_run_server:
            runner = CliRunner()
            result = runner.invoke(cli, ["mcp"])
            assert result.exit_code == 0
            mock_run_server.assert_called_once()


class TestToolPlanToIssueCommand:
    def test_help_shows_issues_dir_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["tool", "plan-to-issue", "--help"])
        assert result.exit_code == 0
        assert "--issues-dir" in result.output
        assert "--todo-dir" not in result.output

    def test_default_issues_dir_is_clasi_issues(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["tool", "plan-to-issue", "--help"])
        assert result.exit_code == 0
        assert ".clasi/issues" in result.output

    def test_plan_to_issue_converts_plan(self, tmp_path):
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        issues_dir = tmp_path / "issues"
        plan_file = plans_dir / "my-plan.md"
        plan_file.write_text("# My Plan\n\nDetails here.\n")

        runner = CliRunner()
        result = runner.invoke(cli, [
            "tool", "plan-to-issue",
            "--plans-dir", str(plans_dir),
            "--issues-dir", str(issues_dir),
        ])
        assert result.exit_code == 0
        assert "issue" in result.output.lower()

    def test_plan_to_issue_no_plan_found(self, tmp_path):
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        issues_dir = tmp_path / "issues"

        runner = CliRunner()
        result = runner.invoke(cli, [
            "tool", "plan-to-issue",
            "--plans-dir", str(plans_dir),
            "--issues-dir", str(issues_dir),
        ])
        assert result.exit_code == 0
        assert "No plan file found" in result.output

    def test_plan_to_todo_subcommand_removed(self):
        """The old plan-to-todo tool subcommand should no longer exist."""
        runner = CliRunner()
        result = runner.invoke(cli, ["tool", "plan-to-todo", "--help"])
        assert result.exit_code != 0
