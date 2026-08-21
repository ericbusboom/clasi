"""Tests for clasi init's platform resolution when no --claude flag is given.

Claude is the only installable platform as of sprint 032 (Codex and
Copilot were archived to the archive/codex-copilot-adapters branch; see
src/clasi/init_command.py). There is no longer a multi-platform choice to
prompt for, so both interactive (TTY) and non-interactive sessions with
no platform flag resolve to Claude-only, with no prompt shown.

Covers:
- Non-interactive path: no prompt, Claude installed by default.
- Interactive path: also no prompt (nothing left to choose among),
  Claude installed by default.
- Explicit --codex/--copilot (interactive or not) never installs
  anything — see test_cli_init.py's TestRunInitArchivedPlatforms /
  TestCliInitFlags for the archived-error coverage.
"""

from unittest.mock import patch

from click.testing import CliRunner

from clasi.cli import cli
from clasi.init_command import run_init


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_claude_artifacts(target):
    return (
        (target / ".claude" / "skills" / "se" / "SKILL.md").exists()
        and (target / "CLAUDE.md").exists()
    )


# ---------------------------------------------------------------------------
# Non-interactive path via run_init directly
# ---------------------------------------------------------------------------


class TestNonInteractivePath:
    """Non-interactive mode (no TTY): no prompt, Claude installed by default."""

    def test_claude_installed_in_non_interactive_mode(self, tmp_path):
        """Non-interactive default installs Claude artifacts."""
        target = tmp_path / "repo"
        target.mkdir()

        with patch("clasi.init_command.sys.stdin.isatty", return_value=False), \
             patch("clasi.init_command.sys.stdout.isatty", return_value=False):
            run_init(str(target))

        assert _has_claude_artifacts(target)

    def test_codex_not_installed_in_non_interactive_mode(self, tmp_path):
        """Non-interactive default does not install Codex artifacts."""
        target = tmp_path / "repo"
        target.mkdir()

        with patch("clasi.init_command.sys.stdin.isatty", return_value=False), \
             patch("clasi.init_command.sys.stdout.isatty", return_value=False):
            run_init(str(target))

        assert not (target / ".codex").exists()
        # AGENTS.md IS created by Claude install (authoritative instruction file).
        assert (target / "AGENTS.md").exists()


# ---------------------------------------------------------------------------
# Interactive path — no platform prompt remains; Claude installs directly
# ---------------------------------------------------------------------------


class TestInteractivePath:
    """Interactive mode (TTY): no platform prompt (only Claude remains),
    Claude installed directly, same as non-interactive."""

    def test_interactive_no_flags_installs_claude(self, tmp_path):
        """Interactive with no flags installs Claude — no prompt fires."""
        target = tmp_path / "repo"
        target.mkdir()

        with patch("clasi.init_command.sys.stdin.isatty", return_value=True), \
             patch("clasi.init_command.sys.stdout.isatty", return_value=True), \
             patch("clasi.init_command._prompt_protected_paths", return_value=[]):
            run_init(str(target))

        assert _has_claude_artifacts(target)
        assert not (target / ".codex").exists()

    def test_interactive_no_flags_no_detect_platforms_call(self, tmp_path):
        """Interactive with no flags never consults detect_platforms —
        there is nothing left to choose among, so no advisory scoring is
        needed to resolve the (single) platform."""
        target = tmp_path / "repo"
        target.mkdir()

        with patch("clasi.init_command.sys.stdin.isatty", return_value=True), \
             patch("clasi.init_command.sys.stdout.isatty", return_value=True), \
             patch("clasi.init_command._prompt_protected_paths", return_value=[]), \
             patch("clasi.platforms.detect.detect_platforms") as mock_detect:
            run_init(str(target))

        mock_detect.assert_not_called()


# ---------------------------------------------------------------------------
# CLI integration — CliRunner is non-interactive (no TTY) by default
# ---------------------------------------------------------------------------


class TestCliNonInteractive:
    """CliRunner tests verify non-interactive behavior through the CLI layer."""

    def test_cli_default_no_flags_installs_claude(self, tmp_path):
        """CliRunner (no TTY) with no flags → Claude installed, no prompt."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert _has_claude_artifacts(tmp_path)
        assert not (tmp_path / ".codex").exists()

    def test_cli_default_no_flags_no_codex(self, tmp_path):
        """CliRunner (no TTY) with no flags → Codex .codex/ absent; AGENTS.md present."""
        runner = CliRunner()
        runner.invoke(cli, ["init", str(tmp_path)])
        assert not (tmp_path / ".codex").exists()
        # AGENTS.md IS created by Claude install (authoritative instruction file).
        assert (tmp_path / "AGENTS.md").exists()
