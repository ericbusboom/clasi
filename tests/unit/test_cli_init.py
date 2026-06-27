"""Tests for --claude / --codex flag handling and 'install' synonym in clasi init.

Verifies that:
- Default (no flags) installs Claude-only artifacts (backward compat).
- --claude installs Claude artifacts only.
- --codex installs Codex artifacts only (no .claude/ or CLAUDE.md).
- --claude --codex installs both sets of artifacts.
- 'clasi install' behaves identically to 'clasi init' with the same flags.
"""

from click.testing import CliRunner

from clasi.cli import cli
from clasi.init_command import run_init


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_claude_artifacts(target):
    """True when the core Claude-owned files are present."""
    return (
        (target / ".claude" / "skills" / "se" / "SKILL.md").exists()
        and (target / "CLAUDE.md").exists()
    )


def _has_codex_artifacts(target):
    """True when the core Codex-owned files are present."""
    return (
        (target / ".codex" / "config.toml").exists()
        and (target / "AGENTS.md").exists()
        and (target / ".agents" / "skills" / "se" / "SKILL.md").exists()
    )


def _has_shared_artifacts(target):
    """True when shared scaffolding is present."""
    from clasi.project import ARTIFACT_PATH_DEFAULTS
    return (
        (target / ARTIFACT_PATH_DEFAULTS["issues"]).exists()
        and (target / ARTIFACT_PATH_DEFAULTS["logs"]).exists()
        and (target / ".mcp.json").exists()
    )


# ---------------------------------------------------------------------------
# run_init direct call tests
# ---------------------------------------------------------------------------

class TestRunInitDefaultInstallsClaudeOnly:
    """run_init() with no flags defaults to Claude-only (backward compat)."""

    def test_claude_artifacts_created(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target))
        assert _has_claude_artifacts(target)

    def test_codex_artifacts_not_created(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target))
        assert not (target / ".codex").exists()
        # AGENTS.md IS created by Claude-only install (it is the authoritative
        # instruction file; CLAUDE.md symlinks to it). Only .codex/ is Codex-specific.
        assert (target / "AGENTS.md").exists()

    def test_shared_artifacts_created(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target))
        assert _has_shared_artifacts(target)


class TestRunInitExplicitClaude:
    """run_init(claude=True, codex=False) installs Claude artifacts only."""

    def test_claude_artifacts_created(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target), claude=True, codex=False)
        assert _has_claude_artifacts(target)

    def test_codex_artifacts_not_created(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target), claude=True, codex=False)
        assert not (target / ".codex").exists()
        # AGENTS.md IS created by Claude-only install (it is the authoritative
        # instruction file; CLAUDE.md symlinks to it). Only .codex/ is Codex-specific.
        assert (target / "AGENTS.md").exists()


class TestRunInitCodexOnly:
    """run_init(claude=False, codex=True) installs Codex artifacts only."""

    def test_codex_artifacts_created(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target), claude=False, codex=True)
        assert _has_codex_artifacts(target)

    def test_claude_artifacts_not_created(self, tmp_path):
        """Claude-specific files must NOT be created in codex-only mode."""
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target), claude=False, codex=True)
        assert not (target / ".claude").exists()
        assert not (target / "CLAUDE.md").exists()

    def test_shared_artifacts_created(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target), claude=False, codex=True)
        assert _has_shared_artifacts(target)


class TestRunInitBoth:
    """run_init(claude=True, codex=True) installs all artifacts."""

    def test_claude_artifacts_created(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target), claude=True, codex=True)
        assert _has_claude_artifacts(target)

    def test_codex_artifacts_created(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target), claude=True, codex=True)
        assert _has_codex_artifacts(target)

    def test_shared_artifacts_created(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target), claude=True, codex=True)
        assert _has_shared_artifacts(target)


# ---------------------------------------------------------------------------
# CLI flag tests via CliRunner
# ---------------------------------------------------------------------------

class TestCliInitFlags:
    """Test --claude / --codex flags through the CLI."""

    def test_init_default_is_claude_only(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert _has_claude_artifacts(tmp_path)
        assert not (tmp_path / ".codex").exists()

    def test_init_claude_flag_installs_claude(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--claude", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert _has_claude_artifacts(tmp_path)
        assert not (tmp_path / ".codex").exists()

    def test_init_codex_flag_installs_codex_only(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--codex", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert _has_codex_artifacts(tmp_path)
        assert not (tmp_path / ".claude").exists()
        assert not (tmp_path / "CLAUDE.md").exists()

    def test_init_both_flags_installs_all(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--claude", "--codex", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert _has_claude_artifacts(tmp_path)
        assert _has_codex_artifacts(tmp_path)


# ---------------------------------------------------------------------------
# 'install' synonym tests via CliRunner
# ---------------------------------------------------------------------------

class TestInstallSynonym:
    """'clasi install' behaves identically to 'clasi init'."""

    def test_install_is_recognized(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["install", str(tmp_path)])
        assert result.exit_code == 0, result.output

    def test_install_default_creates_claude_artifacts(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["install", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert _has_claude_artifacts(tmp_path)
        assert not (tmp_path / ".codex").exists()

    def test_install_codex_flag(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["install", "--codex", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert _has_codex_artifacts(tmp_path)
        assert not (tmp_path / ".claude").exists()
        assert not (tmp_path / "CLAUDE.md").exists()

    def test_install_claude_flag(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["install", "--claude", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert _has_claude_artifacts(tmp_path)
        assert not (tmp_path / ".codex").exists()

    def test_install_both_flags(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["install", "--claude", "--codex", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert _has_claude_artifacts(tmp_path)
        assert _has_codex_artifacts(tmp_path)


# ---------------------------------------------------------------------------
# --copy and --migrate flag tests
# ---------------------------------------------------------------------------

class TestCopyFlag:
    """--copy flag is accepted without error and does not break installs."""

    def test_init_copy_flag_accepted(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--copy", str(tmp_path)])
        assert result.exit_code == 0, result.output

    def test_init_no_copy_flag_accepted(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--no-copy", str(tmp_path)])
        assert result.exit_code == 0, result.output

    def test_init_copy_with_claude_flag(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--claude", "--copy", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert _has_claude_artifacts(tmp_path)

    def test_init_copy_with_codex_flag(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--codex", "--copy", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert _has_codex_artifacts(tmp_path)

    def test_init_copy_with_both_flags(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--claude", "--codex", "--copy", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert _has_claude_artifacts(tmp_path)
        assert _has_codex_artifacts(tmp_path)

    def test_install_synonym_copy_flag_accepted(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["install", "--copy", str(tmp_path)])
        assert result.exit_code == 0, result.output

    def test_run_init_copy_kwarg_accepted(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target), copy=True)
        assert _has_claude_artifacts(target)

    def test_run_init_no_copy_kwarg_accepted(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target), copy=False)
        assert _has_claude_artifacts(target)


class TestMigrateFlag:
    """--migrate flag is accepted without error and does not break installs."""

    def test_init_migrate_flag_accepted(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--migrate", str(tmp_path)])
        assert result.exit_code == 0, result.output

    def test_init_migrate_with_claude_flag(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--claude", "--migrate", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert _has_claude_artifacts(tmp_path)

    def test_init_migrate_with_codex_flag(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--codex", "--migrate", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert _has_codex_artifacts(tmp_path)

    def test_install_synonym_migrate_flag_accepted(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["install", "--migrate", str(tmp_path)])
        assert result.exit_code == 0, result.output

    def test_run_init_migrate_kwarg_accepted(self, tmp_path):
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target), migrate=True)
        assert _has_claude_artifacts(target)

    def test_run_init_copy_and_migrate_coexist(self, tmp_path):
        """--copy and --migrate can both be passed without error."""
        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target), copy=True, migrate=True)
        assert _has_claude_artifacts(target)
