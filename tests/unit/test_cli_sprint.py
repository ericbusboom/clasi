"""Tests for `clasi sprint` CLI group and subcommands."""

from unittest.mock import patch

from click.testing import CliRunner

from clasi.cli import cli


class TestSprintGroup:
    def test_sprint_help_exits_zero(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sprint", "--help"])
        assert result.exit_code == 0

    def test_sprint_help_lists_close(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sprint", "--help"])
        assert "close" in result.output

    def test_sprint_help_shows_docstring(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sprint", "--help"])
        assert "Sprint lifecycle commands" in result.output


class TestSprintCloseHelp:
    def test_close_help_exits_zero(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sprint", "close", "--help"])
        assert result.exit_code == 0

    def test_close_help_shows_sprint_id_argument(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sprint", "close", "--help"])
        assert "SPRINT_ID" in result.output

    def test_close_help_shows_branch_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sprint", "close", "--help"])
        assert "--branch" in result.output

    def test_close_help_shows_main_branch_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sprint", "close", "--help"])
        assert "--main-branch" in result.output

    def test_close_help_shows_push_tags_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sprint", "close", "--help"])
        assert "--push-tags" in result.output
        assert "--no-push-tags" in result.output

    def test_close_help_shows_delete_branch_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sprint", "close", "--help"])
        assert "--delete-branch" in result.output
        assert "--no-delete-branch" in result.output

    def test_close_help_shows_test_command_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sprint", "close", "--help"])
        assert "--test-command" in result.output

    def test_close_help_shows_main_branch_default(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sprint", "close", "--help"])
        assert "master" in result.output


class TestSprintCloseInvocation:
    def test_close_calls_close_sprint_with_sprint_id(self):
        runner = CliRunner()
        with patch("clasi.tools.artifact_tools.close_sprint", return_value="done") as mock_close:
            result = runner.invoke(cli, ["sprint", "close", "007"])
        assert result.exit_code == 0
        mock_close.assert_called_once_with(
            "007", None, "master", True, True, None
        )

    def test_close_calls_close_sprint_with_branch(self):
        runner = CliRunner()
        with patch("clasi.tools.artifact_tools.close_sprint", return_value="done") as mock_close:
            result = runner.invoke(cli, [
                "sprint", "close", "007",
                "--branch", "sprint/007-foo",
            ])
        assert result.exit_code == 0
        mock_close.assert_called_once_with(
            "007", "sprint/007-foo", "master", True, True, None
        )

    def test_close_calls_close_sprint_with_all_options(self):
        runner = CliRunner()
        with patch("clasi.tools.artifact_tools.close_sprint", return_value="ok") as mock_close:
            result = runner.invoke(cli, [
                "sprint", "close", "007",
                "--branch", "sprint/007-foo",
                "--main-branch", "main",
                "--no-push-tags",
                "--no-delete-branch",
                "--test-command", "pytest",
            ])
        assert result.exit_code == 0
        mock_close.assert_called_once_with(
            "007", "sprint/007-foo", "main", False, False, "pytest"
        )

    def test_close_echoes_return_value(self):
        runner = CliRunner()
        with patch("clasi.tools.artifact_tools.close_sprint", return_value="Sprint 007 closed successfully."):
            result = runner.invoke(cli, ["sprint", "close", "007"])
        assert result.exit_code == 0
        assert "Sprint 007 closed successfully." in result.output

    def test_close_requires_sprint_id(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sprint", "close"])
        assert result.exit_code != 0
