"""Tests for clasi/uninstall_command.py and the `clasi uninstall` CLI command.

Covers:
- --claude removes Claude artifacts.
- --codex/--copilot are still accepted by the CLI but raise a clear
  "archived" error instead of removing anything or silently no-op'ing
  (Codex and Copilot were archived to the archive/codex-copilot-adapters
  branch in sprint 032 — see src/clasi/uninstall_command.py).
- Non-interactive, no flag: exits with error.
- Interactive, no flag: prompts (mocked), confirms Claude removal.
- Idempotency: running uninstall twice does not error.
- User content preservation: CLAUDE.md and AGENTS.md user sections survive.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from clasi.cli import cli
from clasi.platforms.claude import install as claude_install


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_MCP_CONFIG = {
    "command": "clasi",
    "args": ["mcp"],
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Return a fresh empty project directory."""
    d = tmp_path / "project"
    d.mkdir()
    return d


@pytest.fixture
def claude_installed(project: Path) -> Path:
    """Install Claude into *project*; return the project path."""
    claude_install(project, _MCP_CONFIG)
    return project


# ---------------------------------------------------------------------------
# Helper: check Claude artifacts absent / present
# ---------------------------------------------------------------------------

def _claude_artifacts_absent(project: Path) -> None:
    """Assert all CLASI-managed Claude artifacts are removed."""
    claude_md = project / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
        assert "<!-- CLASI:START -->" not in content, "CLASI section should be gone from CLAUDE.md"
        assert "<!-- CLASI:END -->" not in content


# ---------------------------------------------------------------------------
# run_uninstall() direct tests
# ---------------------------------------------------------------------------


def test_uninstall_claude_removes_claude_artifacts(claude_installed: Path) -> None:
    """--claude removes Claude artifacts."""
    project = claude_installed
    from clasi.uninstall_command import run_uninstall

    run_uninstall(str(project), claude=True)

    _claude_artifacts_absent(project)


def test_uninstall_non_interactive_no_flag_exits_with_error(project: Path) -> None:
    """Non-interactive mode with no flag exits 1 with a clear error message."""
    from clasi.uninstall_command import run_uninstall

    # Force non-interactive by patching isatty to return False
    with patch("sys.stdin") as mock_stdin, patch("sys.stdout") as mock_stdout:
        mock_stdin.isatty.return_value = False
        mock_stdout.isatty.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            run_uninstall(str(project), claude=False)

    assert exc_info.value.code == 1


def test_uninstall_interactive_no_flag_prompts(project: Path) -> None:
    """Interactive mode with no flag calls _prompt_uninstall and dispatches."""
    from clasi.uninstall_command import run_uninstall

    # Install Claude so there is something to remove.
    claude_install(project, _MCP_CONFIG)

    # Patch the isatty calls at the module level in uninstall_command so we
    # don't have to replace sys.stdin/stdout entirely (which breaks click.echo).
    with patch("clasi.uninstall_command.sys") as mock_sys:
        mock_sys.stdin.isatty.return_value = True
        mock_sys.stdout.isatty.return_value = True

        with patch("clasi.uninstall_command._prompt_uninstall", return_value="claude") as mock_prompt:
            run_uninstall(str(project), claude=False)

    mock_prompt.assert_called_once()

    # Claude artifacts should be removed
    _claude_artifacts_absent(project)


def test_uninstall_idempotent_claude(claude_installed: Path) -> None:
    """Running --claude uninstall twice does not raise an error."""
    project = claude_installed
    from clasi.uninstall_command import run_uninstall

    run_uninstall(str(project), claude=True)
    # Second call is idempotent — should not raise
    run_uninstall(str(project), claude=True)


def test_uninstall_never_installed_is_noop(project: Path) -> None:
    """Uninstalling a platform that was never installed is a no-op (no error)."""
    from clasi.uninstall_command import run_uninstall

    # No install step — Claude is absent
    run_uninstall(str(project), claude=True)


# ---------------------------------------------------------------------------
# Archived platforms: --codex/--copilot raise a clear error
# ---------------------------------------------------------------------------


def test_run_uninstall_codex_true_raises_click_exception(project: Path) -> None:
    from clasi.uninstall_command import run_uninstall

    with pytest.raises(click.ClickException, match="archived"):
        run_uninstall(str(project), codex=True)


def test_run_uninstall_copilot_true_raises_click_exception(project: Path) -> None:
    from clasi.uninstall_command import run_uninstall

    with pytest.raises(click.ClickException, match="archived"):
        run_uninstall(str(project), copilot=True)


def test_run_uninstall_codex_true_error_mentions_archive_branch(project: Path) -> None:
    from clasi.uninstall_command import run_uninstall

    with pytest.raises(click.ClickException) as exc_info:
        run_uninstall(str(project), codex=True)
    assert "archive/codex-copilot-adapters" in str(exc_info.value)


def test_cli_uninstall_codex_flag_exits_nonzero_with_clear_message(claude_installed: Path) -> None:
    """CLI `clasi uninstall --codex` does not crash and does not silently
    no-op — it exits nonzero with a message pointing at the archive branch,
    and leaves Claude artifacts untouched."""
    runner = CliRunner()
    result = runner.invoke(cli, ["uninstall", str(claude_installed), "--codex"])
    assert result.exit_code != 0
    assert "archive" in result.output.lower()

    # Claude artifacts must be untouched — the archived flag must not
    # silently uninstall Claude either.
    claude_md = claude_installed / "CLAUDE.md"
    assert claude_md.exists()
    assert "<!-- CLASI:START -->" in claude_md.read_text(encoding="utf-8")


def test_cli_uninstall_copilot_flag_exits_nonzero_with_clear_message(claude_installed: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["uninstall", str(claude_installed), "--copilot"])
    assert result.exit_code != 0
    assert "archive" in result.output.lower()


# ---------------------------------------------------------------------------
# User content preservation
# ---------------------------------------------------------------------------


def test_uninstall_agents_md_user_content_preserved_on_claude_uninstall(
    project: Path,
) -> None:
    """User content in AGENTS.md outside the CLASI block survives --claude uninstall."""
    # Write user content to AGENTS.md first; install appends the CLASI block.
    user_section = "# My Project Notes\n\nThis is user-owned content.\n"
    agents_md = project / "AGENTS.md"
    agents_md.write_text(user_section, encoding="utf-8")

    claude_install(project, _MCP_CONFIG)

    # After install, AGENTS.md has user content + CLASI block
    content = agents_md.read_text(encoding="utf-8")
    assert "My Project Notes" in content
    assert "<!-- CLASI:START -->" in content

    from clasi.uninstall_command import run_uninstall
    run_uninstall(str(project), claude=True)

    # AGENTS.md must still exist with user content; CLASI block stripped.
    assert agents_md.exists(), "AGENTS.md should still exist when user content is present"
    content = agents_md.read_text(encoding="utf-8")
    assert "My Project Notes" in content, "User content must survive uninstall"
    assert "user-owned content" in content
    assert "<!-- CLASI:START -->" not in content
    assert "<!-- CLASI:END -->" not in content


def test_uninstall_does_not_touch_docs_clasi(claude_installed: Path) -> None:
    """Uninstall never removes docs/clasi/ or its contents."""
    project = claude_installed

    # Create a docs/clasi/todo directory with a user file alongside the
    # AGENTS.md that install already created.
    todo_dir = project / "docs" / "clasi" / "todo"
    todo_dir.mkdir(parents=True, exist_ok=True)
    todo_file = todo_dir / "sample-todo.md"
    todo_file.write_text("---\nstatus: pending\n---\n# A TODO\n", encoding="utf-8")

    from clasi.uninstall_command import run_uninstall
    run_uninstall(str(project), claude=True)

    assert todo_file.exists(), "docs/clasi/todo/sample-todo.md must not be touched by uninstall"


# ---------------------------------------------------------------------------
# CLI integration tests (via click.testing.CliRunner)
# ---------------------------------------------------------------------------


def test_cli_uninstall_claude_flag(claude_installed: Path) -> None:
    """CLI `clasi uninstall --claude` removes Claude artifacts."""
    runner = CliRunner()
    result = runner.invoke(cli, ["uninstall", str(claude_installed), "--claude"])
    assert result.exit_code == 0, f"Expected exit 0, got: {result.output}"
    _claude_artifacts_absent(claude_installed)


def test_cli_uninstall_no_flag_non_interactive_error(project: Path) -> None:
    """CLI `clasi uninstall` with no flags in non-interactive mode exits 1."""
    runner = CliRunner()
    # CliRunner uses non-TTY by default
    result = runner.invoke(cli, ["uninstall", str(project)])
    assert result.exit_code == 1
    assert "specify" in result.output.lower() or "--claude" in result.output


def test_cli_uninstall_help(project: Path) -> None:
    """CLI `clasi uninstall --help` exits 0 and mentions the flags."""
    runner = CliRunner()
    result = runner.invoke(cli, ["uninstall", "--help"])
    assert result.exit_code == 0
    assert "--claude" in result.output
    assert "--codex" in result.output


# ---------------------------------------------------------------------------
# --copy flag on uninstall
# ---------------------------------------------------------------------------


def test_cli_uninstall_copy_flag_accepted(claude_installed: Path) -> None:
    """CLI `clasi uninstall --copy --claude` is accepted without error."""
    runner = CliRunner()
    result = runner.invoke(cli, ["uninstall", str(claude_installed), "--claude", "--copy"])
    assert result.exit_code == 0, f"Expected exit 0, got: {result.output}"
    _claude_artifacts_absent(claude_installed)


def test_cli_uninstall_no_copy_flag_accepted(claude_installed: Path) -> None:
    """CLI `clasi uninstall --no-copy --claude` is accepted without error."""
    runner = CliRunner()
    result = runner.invoke(cli, ["uninstall", str(claude_installed), "--claude", "--no-copy"])
    assert result.exit_code == 0, f"Expected exit 0, got: {result.output}"
    _claude_artifacts_absent(claude_installed)


def test_run_uninstall_copy_kwarg_accepted(claude_installed: Path) -> None:
    """run_uninstall() accepts copy=True without error."""
    from clasi.uninstall_command import run_uninstall

    run_uninstall(str(claude_installed), claude=True, copy=True)
    _claude_artifacts_absent(claude_installed)


def test_run_uninstall_no_copy_kwarg_accepted(claude_installed: Path) -> None:
    """run_uninstall() accepts copy=False (default) without error."""
    from clasi.uninstall_command import run_uninstall

    run_uninstall(str(claude_installed), claude=True, copy=False)
    _claude_artifacts_absent(claude_installed)


def test_cli_uninstall_help_mentions_copy(project: Path) -> None:
    """CLI `clasi uninstall --help` mentions --copy flag."""
    runner = CliRunner()
    result = runner.invoke(cli, ["uninstall", "--help"])
    assert result.exit_code == 0
    assert "--copy" in result.output
