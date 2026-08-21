"""Tests for interactive platform prompt in clasi init.

Covers:
- Non-interactive path: no prompt, Claude installed by default.
- Interactive path with Claude recommendation: prompt shown, user picks 1.
- Interactive path with Codex recommendation: prompt shown, user picks 2.
- Interactive path with both recommendation: prompt shown, user picks 3.
"""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from clasi.cli import cli
from clasi.init_command import _prompt_platform, run_init
from clasi.platforms.detect import PlatformSignals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_claude_artifacts(target):
    return (
        (target / ".claude" / "skills" / "se" / "SKILL.md").exists()
        and (target / "CLAUDE.md").exists()
    )


def _has_codex_artifacts(target):
    return (
        (target / ".codex" / "config.toml").exists()
        and (target / "AGENTS.md").exists()
        and (target / ".agents" / "skills" / "se" / "SKILL.md").exists()
    )


def _make_signals(recommendation):
    """Build a PlatformSignals with scores that match the recommendation."""
    if recommendation == "claude":
        return PlatformSignals(claude_score=2, codex_score=0, copilot_score=0, recommendation="claude")
    if recommendation == "codex":
        return PlatformSignals(claude_score=0, codex_score=2, copilot_score=0, recommendation="codex")
    if recommendation == "copilot":
        return PlatformSignals(claude_score=0, codex_score=0, copilot_score=2, recommendation="copilot")
    # both
    return PlatformSignals(claude_score=2, codex_score=2, copilot_score=0, recommendation="both")


# ---------------------------------------------------------------------------
# _prompt_platform unit tests
# ---------------------------------------------------------------------------


class TestPromptPlatform:
    """Unit tests for the _prompt_platform helper."""

    def test_claude_recommendation_returns_claude_on_1(self):
        with patch("clasi.init_command.click.prompt", return_value="1"), \
             patch("clasi.init_command.click.echo"):
            choice = _prompt_platform("claude")
        assert choice == "claude"

    def test_codex_recommendation_returns_codex_on_2(self):
        with patch("clasi.init_command.click.prompt", return_value="2"), \
             patch("clasi.init_command.click.echo"):
            choice = _prompt_platform("codex")
        assert choice == "codex"

    def test_copilot_recommendation_returns_copilot_on_3(self):
        with patch("clasi.init_command.click.prompt", return_value="3"), \
             patch("clasi.init_command.click.echo"):
            choice = _prompt_platform("copilot")
        assert choice == "copilot"

    def test_both_recommendation_returns_both_on_4(self):
        with patch("clasi.init_command.click.prompt", return_value="4"), \
             patch("clasi.init_command.click.echo"):
            choice = _prompt_platform("both")
        assert choice == "both"

    def test_claude_recommendation_shown_in_echo(self):
        echoed = []
        with patch("clasi.init_command.click.prompt", return_value="1"), \
             patch("clasi.init_command.click.echo", side_effect=echoed.append):
            _prompt_platform("claude")
        assert any("recommended: Claude" in str(m) for m in echoed)

    def test_codex_recommendation_shown_in_echo(self):
        echoed = []
        with patch("clasi.init_command.click.prompt", return_value="2"), \
             patch("clasi.init_command.click.echo", side_effect=echoed.append):
            _prompt_platform("codex")
        assert any("recommended: Codex" in str(m) for m in echoed)

    def test_both_recommendation_shown_in_echo(self):
        echoed = []
        with patch("clasi.init_command.click.prompt", return_value="4"), \
             patch("clasi.init_command.click.echo", side_effect=echoed.append):
            _prompt_platform("both")
        assert any("recommended: All three" in str(m) for m in echoed)

    def test_prompt_shows_all_four_options(self):
        echoed = []
        with patch("clasi.init_command.click.prompt", return_value="1"), \
             patch("clasi.init_command.click.echo", side_effect=echoed.append):
            _prompt_platform("claude")
        combined = " ".join(str(m) for m in echoed)
        assert "Claude" in combined
        assert "Codex" in combined
        assert "Copilot" in combined
        assert "All three" in combined


# ---------------------------------------------------------------------------
# Non-interactive path via run_init directly
# ---------------------------------------------------------------------------


class TestNonInteractivePath:
    """Non-interactive mode (no TTY): no prompt, Claude installed by default."""

    def test_no_prompt_called_in_non_interactive_mode(self, tmp_path):
        """With no TTY, _prompt_platform is never called."""
        target = tmp_path / "repo"
        target.mkdir()

        with patch("clasi.init_command.sys.stdin.isatty", return_value=False), \
             patch("clasi.init_command.sys.stdout.isatty", return_value=False), \
             patch("clasi.init_command._prompt_platform") as mock_prompt:
            run_init(str(target))

        mock_prompt.assert_not_called()

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
# Interactive path — user selects each option
# ---------------------------------------------------------------------------


class TestInteractivePath:
    """Interactive mode (TTY): prompt shown, user selection drives install."""

    def _run_interactive(self, target, recommendation, user_choice):
        """Helper: simulate TTY with a mocked detect and prompt.

        Also mocks _prompt_protected_paths (ticket 031-004): these fixture
        targets are empty dirs with no src/tests to auto-detect, so
        without this the unrelated interactive protected_paths prompt
        would also fire and hit real stdin (unmocked) under pytest's
        capture. Declining (returning []) keeps this helper scoped to
        what it's actually testing — platform selection.
        """
        fake_signals = _make_signals(recommendation)

        with patch("clasi.init_command.sys.stdin.isatty", return_value=True), \
             patch("clasi.init_command.sys.stdout.isatty", return_value=True), \
             patch("clasi.platforms.detect.detect_platforms", return_value=fake_signals) as mock_detect, \
             patch("clasi.init_command._prompt_platform", return_value=user_choice) as mock_prompt, \
             patch("clasi.init_command._prompt_protected_paths", return_value=[]):
            run_init(str(target))

        return mock_detect, mock_prompt

    def test_interactive_claude_recommendation_user_picks_claude(self, tmp_path):
        """Interactive: recommendation=claude, user selects 1 → Claude installed."""
        target = tmp_path / "repo"
        target.mkdir()

        mock_detect, mock_prompt = self._run_interactive(target, "claude", "claude")

        mock_prompt.assert_called_once_with("claude")
        assert _has_claude_artifacts(target)
        assert not (target / ".codex").exists()

    def test_interactive_codex_recommendation_user_picks_codex(self, tmp_path):
        """Interactive: recommendation=codex, user selects 2 → Codex installed."""
        target = tmp_path / "repo"
        target.mkdir()

        mock_detect, mock_prompt = self._run_interactive(target, "codex", "codex")

        mock_prompt.assert_called_once_with("codex")
        assert _has_codex_artifacts(target)
        assert not (target / ".claude").exists()
        assert not (target / "CLAUDE.md").exists()

    def test_interactive_both_recommendation_user_picks_both(self, tmp_path):
        """Interactive: recommendation=both, user selects 3 → both installed."""
        target = tmp_path / "repo"
        target.mkdir()

        mock_detect, mock_prompt = self._run_interactive(target, "both", "both")

        mock_prompt.assert_called_once_with("both")
        assert _has_claude_artifacts(target)
        assert _has_codex_artifacts(target)

    def test_interactive_prompt_receives_recommendation(self, tmp_path):
        """The recommendation from detect_platforms is passed to _prompt_platform."""
        target = tmp_path / "repo"
        target.mkdir()

        mock_detect, mock_prompt = self._run_interactive(target, "codex", "codex")

        mock_prompt.assert_called_once_with("codex")

    def test_interactive_no_prompt_when_claude_flag_supplied(self, tmp_path):
        """Even in interactive mode, no prompt fires when --claude is given."""
        target = tmp_path / "repo"
        target.mkdir()

        with patch("clasi.init_command.sys.stdin.isatty", return_value=True), \
             patch("clasi.init_command.sys.stdout.isatty", return_value=True), \
             patch("clasi.init_command._prompt_platform") as mock_prompt, \
             patch("clasi.init_command._prompt_protected_paths", return_value=[]):
            run_init(str(target), claude=True)

        mock_prompt.assert_not_called()

    def test_interactive_no_prompt_when_codex_flag_supplied(self, tmp_path):
        """Even in interactive mode, no prompt fires when --codex is given."""
        target = tmp_path / "repo"
        target.mkdir()

        with patch("clasi.init_command.sys.stdin.isatty", return_value=True), \
             patch("clasi.init_command.sys.stdout.isatty", return_value=True), \
             patch("clasi.init_command._prompt_platform") as mock_prompt, \
             patch("clasi.init_command._prompt_protected_paths", return_value=[]):
            run_init(str(target), codex=True)

        mock_prompt.assert_not_called()


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
