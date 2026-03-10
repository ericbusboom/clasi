"""Tests for the CLASI CLI entry point."""

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from claude_agent_skills.cli import cli


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
        # Should create /se skill stub
        assert (tmp_path / ".claude" / "skills" / "se" / "SKILL.md").is_file()
        # Should create CLAUDE.md with inline CLASI block
        assert (tmp_path / "CLAUDE.md").is_file()

    def test_init_default_target_uses_cwd(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0
            assert Path("CLAUDE.md").is_file()

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


class TestTodoSplitCommand:
    def test_no_files_to_split(self, tmp_path):
        todo_dir = tmp_path / "todo"
        todo_dir.mkdir()
        runner = CliRunner()
        result = runner.invoke(cli, ["todo-split", str(todo_dir)])
        assert result.exit_code == 0
        assert "No files needed splitting" in result.output

    def test_splits_multi_heading_file(self, tmp_path):
        todo_dir = tmp_path / "todo"
        todo_dir.mkdir()
        (todo_dir / "multi.md").write_text(
            "# First Thing\n\nDetails.\n\n# Second Thing\n\nMore details.\n"
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["todo-split", str(todo_dir)])
        assert result.exit_code == 0
        assert "TODO split results" in result.output
        # Original file should be deleted, two new files created
        assert not (todo_dir / "multi.md").exists()
        assert (todo_dir / "first-thing.md").is_file()
        assert (todo_dir / "second-thing.md").is_file()

    def test_nonexistent_directory_fails(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["todo-split", "/nonexistent/path"])
        assert result.exit_code != 0


class TestMcpCommand:
    def test_mcp_calls_run_server(self):
        with patch(
            "claude_agent_skills.mcp_server.run_server",
        ) as mock_run_server:
            runner = CliRunner()
            result = runner.invoke(cli, ["mcp"])
            assert result.exit_code == 0
            mock_run_server.assert_called_once()
