"""End-to-end tests for the migrate-prompt wiring in clasi init.

Tests in this module exercise the detect-and-prompt flow that was added
in ticket 013-008:
- ``run_init`` calls ``detect_moves`` after scaffolding.
- If moves are pending and the process is interactive (TTY), it prints
  proposed moves and calls ``click.confirm``.
- Non-interactive (no TTY) warns only — does NOT move files.
- ``--yes / --relocate`` flag skips the prompt and relocates immediately.
- ``clasi migrate --yes`` also relocates without prompting.

All tests use scratch directories (``tmp_path``).  This repo's own
``.clasi/`` is never touched.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from clasi.cli import cli
from clasi.init_command import run_init
from clasi.migrate_command import run_migrate
from clasi.project import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_legacy_issues(root: Path, filename: str = "idea.md") -> Path:
    """Create a file at the legacy .clasi/issues/ location and return its path."""
    legacy_dir = root / ".clasi" / "issues"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_file = legacy_dir / filename
    legacy_file.write_text("# Legacy issue", encoding="utf-8")
    return legacy_file


# ---------------------------------------------------------------------------
# Test: interactive prompt moves files when user answers y
# ---------------------------------------------------------------------------


class TestInitPromptsWhenLegacyFilesFound:
    """When init is run on a repo with legacy files and a TTY is present,
    the user should be prompted to move them."""

    def test_prompts_and_moves_on_yes(self, tmp_path: Path, monkeypatch) -> None:
        """Answering 'y' at the confirm prompt causes execute_moves to run."""
        legacy_file = _seed_legacy_issues(tmp_path)

        # Monkeypatch click.confirm to return True (user pressed y).
        monkeypatch.setattr("click.confirm", lambda *args, **kwargs: True)

        # Patch isatty at the module level in init_command to avoid replacing
        # sys.stdout (which causes Click's echo to fail).
        with patch("clasi.init_command.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            mock_sys.stdout.isatty.return_value = True
            with patch("clasi.migrate_command._is_git_repo", return_value=False):
                run_init(str(tmp_path), claude=True)

        project = Project(tmp_path)
        assert (project.issues_dir / "idea.md").exists(), (
            "File should have been moved to the configured issues_dir"
        )
        assert not legacy_file.exists(), "Legacy file should be gone after move"

    def test_proposed_moves_printed_before_confirm(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """The src → dst listing is printed before the confirmation prompt."""
        _seed_legacy_issues(tmp_path)

        monkeypatch.setattr("click.confirm", lambda *args, **kwargs: False)

        with patch("clasi.init_command.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            mock_sys.stdout.isatty.return_value = True
            with patch("clasi.migrate_command._is_git_repo", return_value=False):
                run_init(str(tmp_path), claude=True)

        captured = capsys.readouterr()
        # The message "Your files are not in the right spot" should appear.
        assert "not in the right spot" in captured.out or "Proposed moves" in captured.out


# ---------------------------------------------------------------------------
# Test: answering N leaves files untouched + hint is printed
# ---------------------------------------------------------------------------


class TestInitNoAnswerLeavesFilesUntouched:
    def test_no_answer_leaves_legacy_file(self, tmp_path: Path, monkeypatch) -> None:
        """Answering 'n' at the confirm prompt leaves files in place."""
        legacy_file = _seed_legacy_issues(tmp_path)

        monkeypatch.setattr("click.confirm", lambda *args, **kwargs: False)

        with patch("clasi.init_command.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            mock_sys.stdout.isatty.return_value = True
            with patch("clasi.migrate_command._is_git_repo", return_value=False):
                run_init(str(tmp_path), claude=True)

        assert legacy_file.exists(), "File should remain after user declines move"

    def test_no_answer_prints_hint(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """Answering 'n' prints a hint about 'clasi migrate'."""
        _seed_legacy_issues(tmp_path)

        monkeypatch.setattr("click.confirm", lambda *args, **kwargs: False)

        with patch("clasi.init_command.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            mock_sys.stdout.isatty.return_value = True
            with patch("clasi.migrate_command._is_git_repo", return_value=False):
                run_init(str(tmp_path), claude=True)

        captured = capsys.readouterr()
        assert "clasi migrate" in captured.out


# ---------------------------------------------------------------------------
# Test: non-interactive (no TTY) — warns only, does NOT move
# ---------------------------------------------------------------------------


class TestInitWarnOnlyNonInteractive:
    def test_non_interactive_warns_and_does_not_move(
        self, tmp_path: Path, capsys
    ) -> None:
        """When no TTY is attached, init warns but does NOT move files."""
        legacy_file = _seed_legacy_issues(tmp_path)

        # Patch sys in init_command module to simulate non-interactive.
        with patch("clasi.init_command.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            mock_sys.stdout.isatty.return_value = False
            with patch("clasi.migrate_command._is_git_repo", return_value=False):
                run_init(str(tmp_path), claude=True)

        # File must NOT have been moved.
        assert legacy_file.exists(), (
            "Non-interactive: legacy file must NOT be moved without explicit --yes"
        )

        # A warning must have been printed to stderr.
        captured = capsys.readouterr()
        assert "WARNING" in captured.err or "legacy" in captured.err.lower(), (
            f"Expected a warning in stderr, got: {captured.err!r}"
        )

    def test_non_interactive_no_confirm_called(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """click.confirm must NOT be called in non-interactive mode."""
        _seed_legacy_issues(tmp_path)

        confirm_called = []

        def _fake_confirm(*args, **kwargs):
            confirm_called.append(True)
            return False

        monkeypatch.setattr("click.confirm", _fake_confirm)

        with patch("clasi.init_command.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            mock_sys.stdout.isatty.return_value = False
            with patch("clasi.migrate_command._is_git_repo", return_value=False):
                run_init(str(tmp_path), claude=True)

        assert not confirm_called, "click.confirm must not be called in non-interactive mode"


# ---------------------------------------------------------------------------
# Test: --yes flag skips prompt and relocates immediately
# ---------------------------------------------------------------------------


class TestInitYesFlagSkipsPrompt:
    def test_yes_flag_relocates_without_prompt(self, tmp_path: Path, monkeypatch) -> None:
        """run_init(yes=True) relocates without calling click.confirm."""
        legacy_file = _seed_legacy_issues(tmp_path)

        confirm_called = []

        def _fake_confirm(*args, **kwargs):
            confirm_called.append(True)
            return True

        monkeypatch.setattr("click.confirm", _fake_confirm)

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            run_init(str(tmp_path), claude=True, yes=True)

        project = Project(tmp_path)
        assert (project.issues_dir / "idea.md").exists(), (
            "--yes should move the file"
        )
        assert not legacy_file.exists(), "Legacy file should be gone after --yes move"
        assert not confirm_called, (
            "click.confirm must NOT be called when yes=True"
        )

    def test_yes_flag_works_non_interactive(self, tmp_path: Path) -> None:
        """--yes overrides the TTY check and relocates even in non-interactive mode."""
        legacy_file = _seed_legacy_issues(tmp_path)

        # Patch sys to simulate non-interactive environment.
        with patch("clasi.init_command.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            mock_sys.stdout.isatty.return_value = False
            with patch("clasi.migrate_command._is_git_repo", return_value=False):
                run_init(str(tmp_path), claude=True, yes=True)

        project = Project(tmp_path)
        assert (project.issues_dir / "idea.md").exists(), (
            "--yes should move the file even in non-interactive mode"
        )
        assert not legacy_file.exists()

    def test_cli_init_yes_flag_accepted(self, tmp_path: Path) -> None:
        """clasi init --yes is accepted by the CLI without error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--yes", str(tmp_path)])
        assert result.exit_code == 0, result.output

    def test_cli_init_relocate_flag_accepted(self, tmp_path: Path) -> None:
        """clasi init --relocate is accepted by the CLI (alias for --yes)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--relocate", str(tmp_path)])
        assert result.exit_code == 0, result.output

    def test_cli_init_yes_flag_relocates(self, tmp_path: Path) -> None:
        """clasi init --yes moves legacy files via the CLI."""
        legacy_file = _seed_legacy_issues(tmp_path)

        runner = CliRunner()
        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            result = runner.invoke(cli, ["init", "--yes", "--claude", str(tmp_path)])

        assert result.exit_code == 0, result.output
        project = Project(tmp_path)
        assert (project.issues_dir / "idea.md").exists(), (
            f"File should be at issues_dir after --yes. CLI output:\n{result.output}"
        )
        assert not legacy_file.exists()


# ---------------------------------------------------------------------------
# Test: clasi migrate --yes (or --relocate) relocates without prompting
# ---------------------------------------------------------------------------


class TestMigrateYesFlag:
    def test_run_migrate_yes_flag_relocates(self, tmp_path: Path, monkeypatch) -> None:
        """run_migrate(yes=True) moves legacy files without prompting."""
        legacy_file = _seed_legacy_issues(tmp_path)

        confirm_called = []
        monkeypatch.setattr("click.confirm", lambda *a, **kw: confirm_called.append(True) or True)

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init"):
                run_migrate(str(tmp_path), yes=True)

        project = Project(tmp_path)
        assert (project.issues_dir / "idea.md").exists(), (
            "run_migrate(yes=True) should move the file"
        )
        assert not legacy_file.exists()
        assert not confirm_called, (
            "click.confirm must not be called when yes=True on run_migrate"
        )

    def test_cli_migrate_yes_flag_accepted(self, tmp_path: Path) -> None:
        """clasi migrate --yes is accepted by the CLI without error."""
        runner = CliRunner()
        with patch("clasi.migrate_command.run_init"):
            result = runner.invoke(cli, ["migrate", "--yes", str(tmp_path)])
        assert result.exit_code == 0, result.output

    def test_cli_migrate_relocate_flag_accepted(self, tmp_path: Path) -> None:
        """clasi migrate --relocate is accepted by the CLI (alias for --yes)."""
        runner = CliRunner()
        with patch("clasi.migrate_command.run_init"):
            result = runner.invoke(cli, ["migrate", "--relocate", str(tmp_path)])
        assert result.exit_code == 0, result.output

    def test_cli_migrate_yes_flag_moves_files(self, tmp_path: Path) -> None:
        """clasi migrate --yes moves legacy files via the CLI."""
        legacy_file = _seed_legacy_issues(tmp_path)

        runner = CliRunner()
        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init"):
                result = runner.invoke(cli, ["migrate", "--yes", str(tmp_path)])

        assert result.exit_code == 0, result.output
        project = Project(tmp_path)
        assert (project.issues_dir / "idea.md").exists(), (
            f"File should have moved. CLI output:\n{result.output}"
        )
        assert not legacy_file.exists()


# ---------------------------------------------------------------------------
# Test: no moves on a clean install (no legacy files)
# ---------------------------------------------------------------------------


class TestNoMovesOnCleanInstall:
    def test_no_prompt_when_no_legacy_files(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """When no legacy files exist, init completes without any migrate prompt."""
        confirm_called = []
        monkeypatch.setattr("click.confirm", lambda *a, **kw: confirm_called.append(True) or False)

        run_init(str(tmp_path), claude=True)

        # No confirmation dialog should have fired.
        assert not confirm_called, (
            "click.confirm must not be called when there are no legacy files"
        )

        # No warning in stderr about legacy locations.
        captured = capsys.readouterr()
        assert "legacy" not in captured.err.lower(), (
            f"No legacy-location warning expected, got stderr: {captured.err!r}"
        )

    def test_clean_install_exit_zero(self, tmp_path: Path) -> None:
        """clasi init on a fresh repo exits cleanly with no migration noise."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--claude", str(tmp_path)])
        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# Test: idempotency — re-running init after a successful migration shows no moves
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_no_moves_after_successful_migrate(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """After files have been moved by --yes, a second init shows no pending moves."""
        _seed_legacy_issues(tmp_path)

        # First run: relocate with --yes.
        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            run_init(str(tmp_path), claude=True, yes=True)

        # Second run: no legacy files remain, so detect_moves should return [].
        from clasi.migrate_command import detect_moves

        project = Project(tmp_path)
        moves = detect_moves(project)
        issues_moves = [m for m in moves if m.category == "issues"]
        assert not issues_moves, (
            "No issues moves should be detected after a successful relocation"
        )

    def test_second_init_no_prompt(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Re-running init after migration does not trigger confirm."""
        _seed_legacy_issues(tmp_path)

        # First run: relocate.
        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            run_init(str(tmp_path), claude=True, yes=True)

        # Second run: simulate interactive mode; confirm must not be called.
        confirm_called = []
        monkeypatch.setattr("click.confirm", lambda *a, **kw: confirm_called.append(True) or False)

        with patch("clasi.init_command.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            mock_sys.stdout.isatty.return_value = True
            with patch("clasi.migrate_command._is_git_repo", return_value=False):
                run_init(str(tmp_path), claude=True)

        assert not confirm_called, (
            "No confirm prompt expected on second init when files are already in place"
        )
