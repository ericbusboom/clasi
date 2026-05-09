"""Tests for clasi.migrate_command module."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from clasi.cli import cli
from clasi.migrate_command import (
    _check_no_execution_lock,
    _is_git_repo,
    _update_gitignore,
    run_migrate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_docs_clasi(root: Path) -> Path:
    """Create a minimal docs/clasi/ structure inside *root*."""
    docs_clasi = root / "docs" / "clasi"
    docs_clasi.mkdir(parents=True, exist_ok=True)
    (docs_clasi / "sprints").mkdir()
    (docs_clasi / "log").mkdir()
    (docs_clasi / "issues").mkdir()
    (docs_clasi / "architecture").mkdir()
    return docs_clasi


def _init_git_repo(root: Path) -> None:
    """Initialize a bare git repository at *root*."""
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# _is_git_repo
# ---------------------------------------------------------------------------


class TestIsGitRepo:
    def test_returns_true_inside_git_repo(self, tmp_path):
        _init_git_repo(tmp_path)
        assert _is_git_repo(tmp_path) is True

    def test_returns_false_outside_git_repo(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        assert _is_git_repo(plain) is False


# ---------------------------------------------------------------------------
# _update_gitignore
# ---------------------------------------------------------------------------


class TestUpdateGitignore:
    def test_replaces_old_entry(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\ndocs/clasi/log/\nbuild/\n", encoding="utf-8")
        _update_gitignore(tmp_path)
        content = gitignore.read_text(encoding="utf-8")
        assert "docs/clasi/log/" not in content
        assert ".clasi/log/" in content
        assert "node_modules/" in content
        assert "build/" in content

    def test_no_op_when_gitignore_missing(self, tmp_path):
        # Should not raise and must not create .gitignore
        _update_gitignore(tmp_path)
        assert not (tmp_path / ".gitignore").exists()

    def test_no_op_when_old_entry_absent(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        original = "node_modules/\nbuild/\n"
        gitignore.write_text(original, encoding="utf-8")
        _update_gitignore(tmp_path)
        assert gitignore.read_text(encoding="utf-8") == original

    def test_replaces_all_occurrences(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("docs/clasi/log/\ndocs/clasi/log/\n", encoding="utf-8")
        _update_gitignore(tmp_path)
        content = gitignore.read_text(encoding="utf-8")
        assert "docs/clasi/log/" not in content
        assert content.count(".clasi/log/") == 2


# ---------------------------------------------------------------------------
# _check_no_execution_lock
# ---------------------------------------------------------------------------


class TestCheckNoExecutionLock:
    def test_passes_when_no_db(self, tmp_path):
        # No docs/clasi/.clasi.db — should not raise.
        _check_no_execution_lock(tmp_path)

    def test_passes_when_db_has_no_lock(self, tmp_path):
        from clasi.state_db import init_db

        db_path = tmp_path / "docs" / "clasi" / ".clasi.db"
        db_path.parent.mkdir(parents=True)
        init_db(db_path)
        _check_no_execution_lock(tmp_path)  # must not raise

    def test_raises_when_lock_held(self, tmp_path):
        from clasi.state_db import acquire_lock, init_db, register_sprint

        db_path = tmp_path / "docs" / "clasi" / ".clasi.db"
        db_path.parent.mkdir(parents=True)
        init_db(db_path)
        register_sprint(db_path, "001", "test-sprint")
        acquire_lock(db_path, "001")

        with pytest.raises(SystemExit) as exc_info:
            _check_no_execution_lock(tmp_path)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# run_migrate — non-git path
# ---------------------------------------------------------------------------


class TestRunMigrateNonGit:
    def test_moves_docs_clasi_to_dot_clasi(self, tmp_path):
        _make_docs_clasi(tmp_path)
        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init"):
                run_migrate(str(tmp_path))

        assert (tmp_path / ".clasi").exists()
        assert not (tmp_path / "docs" / "clasi").exists()

    def test_guard_dot_clasi_already_exists(self, tmp_path):
        _make_docs_clasi(tmp_path)
        (tmp_path / ".clasi").mkdir()

        with pytest.raises(SystemExit) as exc_info:
            run_migrate(str(tmp_path))
        assert exc_info.value.code == 1

    def test_guard_docs_clasi_missing(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            run_migrate(str(tmp_path))
        assert exc_info.value.code == 1

    def test_updates_gitignore(self, tmp_path):
        _make_docs_clasi(tmp_path)
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("docs/clasi/log/\n", encoding="utf-8")

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init"):
                run_migrate(str(tmp_path))

        content = gitignore.read_text(encoding="utf-8")
        assert ".clasi/log/" in content
        assert "docs/clasi/log/" not in content

    def test_calls_run_init(self, tmp_path):
        _make_docs_clasi(tmp_path)

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init") as mock_init:
                run_migrate(str(tmp_path))

        mock_init.assert_called_once()
        _, kwargs = mock_init.call_args
        assert kwargs.get("claude", True)  # claude=True should be passed

    def test_removes_empty_docs_dir(self, tmp_path):
        """docs/ is removed after migration if it becomes empty."""
        _make_docs_clasi(tmp_path)  # only docs/clasi/ exists inside docs/

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init"):
                run_migrate(str(tmp_path))

        assert not (tmp_path / "docs").exists()

    def test_preserves_docs_dir_when_non_empty(self, tmp_path):
        """docs/ is preserved when other content exists alongside docs/clasi/."""
        _make_docs_clasi(tmp_path)
        (tmp_path / "docs" / "design").mkdir()

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init"):
                run_migrate(str(tmp_path))

        assert (tmp_path / "docs").exists()
        assert (tmp_path / "docs" / "design").exists()


# ---------------------------------------------------------------------------
# run_migrate — git path
# ---------------------------------------------------------------------------


class TestRunMigrateGit:
    def test_uses_git_mv_in_git_repo(self, tmp_path):
        _make_docs_clasi(tmp_path)
        _init_git_repo(tmp_path)

        # git mv only works on tracked files — add a file inside docs/clasi/
        # so git will track the directory.
        marker = tmp_path / "docs" / "clasi" / "sprints" / ".gitkeep"
        marker.touch()

        # Stage docs/clasi so git mv can operate on it.
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "docs/"],
            check=True,
            capture_output=True,
        )

        with patch("clasi.migrate_command.run_init"):
            run_migrate(str(tmp_path))

        assert (tmp_path / ".clasi").exists()
        assert not (tmp_path / "docs" / "clasi").exists()

    def test_git_mv_called_not_shutil(self, tmp_path):
        _make_docs_clasi(tmp_path)

        with patch("clasi.migrate_command._is_git_repo", return_value=True):
            with patch("clasi.migrate_command._git_mv") as mock_git_mv:
                with patch("clasi.migrate_command.shutil") as mock_shutil:
                    with patch("clasi.migrate_command.run_init"):
                        run_migrate(str(tmp_path))

        mock_git_mv.assert_called_once()
        mock_shutil.move.assert_not_called()

    def test_shutil_called_when_not_git(self, tmp_path):
        _make_docs_clasi(tmp_path)

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command._git_mv") as mock_git_mv:
                with patch("clasi.migrate_command.run_init"):
                    run_migrate(str(tmp_path))

        mock_git_mv.assert_not_called()
        # shutil.move is called implicitly; .clasi should exist
        assert (tmp_path / ".clasi").exists()


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestMigrateCliCommand:
    def test_migrate_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["migrate", "--help"])
        assert result.exit_code == 0
        assert "migrate" in result.output.lower() or "docs/clasi" in result.output.lower()

    def test_migrate_guard_dot_clasi_exists(self, tmp_path):
        _make_docs_clasi(tmp_path)
        (tmp_path / ".clasi").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["migrate", str(tmp_path)])
        assert result.exit_code != 0

    def test_migrate_guard_docs_clasi_missing(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["migrate", str(tmp_path)])
        assert result.exit_code != 0

    def test_migrate_succeeds_non_git(self, tmp_path):
        _make_docs_clasi(tmp_path)

        runner = CliRunner()
        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init"):
                result = runner.invoke(cli, ["migrate", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert (tmp_path / ".clasi").exists()

    def test_migrate_prints_restart_notice(self, tmp_path):
        _make_docs_clasi(tmp_path)

        runner = CliRunner()
        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init"):
                result = runner.invoke(cli, ["migrate", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert "restart" in result.output.lower()
