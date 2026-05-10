"""
tests/clasr/test_cli.py

Tests for clasr.cli — argument parsing, --instructions flag, validation,
and integration tests for install/uninstall dispatching.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from clasr import __version__
from clasr.cli import main


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _build_asr_fixture(base: Path) -> Path:
    """Build a minimal asr/ fixture tree in *base* and return the asr path.

    Layout:
        asr/
          AGENTS.md
          skills/foo/SKILL.md
          agents/bar.md          (union frontmatter — includes all three platforms)
          rules/baz.md           (union frontmatter)
          claude/extra.md        (passthrough for claude)
          codex/extra.md         (passthrough for codex)
          copilot/extra.md       (passthrough for copilot)
    """
    asr = base / "asr"

    (asr / "skills" / "foo").mkdir(parents=True)
    (asr / "agents").mkdir(parents=True)
    (asr / "rules").mkdir(parents=True)
    (asr / "claude").mkdir(parents=True)
    (asr / "codex").mkdir(parents=True)
    (asr / "copilot").mkdir(parents=True)

    (asr / "AGENTS.md").write_text("# Agents\n\nShared agent instructions.\n", encoding="utf-8")
    (asr / "skills" / "foo" / "SKILL.md").write_text("# Foo skill\n", encoding="utf-8")

    agent_content = (
        "---\n"
        "name: bar\n"
        "description: bar agent\n"
        "claude:\n"
        "  tools: [Read]\n"
        "codex: {}\n"
        "copilot:\n"
        "  applyTo: '**/*.py'\n"
        "---\n"
        "# Bar agent body\n"
    )
    (asr / "agents" / "bar.md").write_text(agent_content, encoding="utf-8")

    rule_content = (
        "---\n"
        "name: baz\n"
        "description: baz rule\n"
        "claude: {}\n"
        "codex: {}\n"
        "copilot: {}\n"
        "---\n"
        "# Baz rule body\n"
    )
    (asr / "rules" / "baz.md").write_text(rule_content, encoding="utf-8")

    (asr / "claude" / "extra.md").write_text("# Claude passthrough\n", encoding="utf-8")
    (asr / "codex" / "extra.md").write_text("# Codex passthrough\n", encoding="utf-8")
    (asr / "copilot" / "extra.md").write_text("# Copilot passthrough\n", encoding="utf-8")

    return asr


# ---------------------------------------------------------------------------
# --instructions
# ---------------------------------------------------------------------------


def test_instructions_prints_nonempty_content(capsys: pytest.CaptureFixture[str]) -> None:
    """--instructions should print non-empty content and return 0."""
    rc = main(["--instructions"])
    captured = capsys.readouterr()
    assert rc == 0
    assert len(captured.out) > 0
    # Should contain something recognisable from instructions.md
    assert "clasr" in captured.out.lower()


def test_instructions_via_subprocess() -> None:
    """Verify --instructions works end-to-end through the installed entry point."""
    result = subprocess.run(
        [sys.executable, "-m", "clasr.cli", "--instructions"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert len(result.stdout) > 0


def test_version_via_subprocess() -> None:
    """Verify --version works end-to-end through the installed entry point."""
    result = subprocess.run(
        [sys.executable, "-m", "clasr.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == f"clasr {__version__}"


# ---------------------------------------------------------------------------
# install --help
# ---------------------------------------------------------------------------


def test_install_help_shows_all_flags() -> None:
    """clasr install --help should list all documented flags."""
    result = subprocess.run(
        [sys.executable, "-m", "clasr.cli", "install", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    help_text = result.stdout
    for flag in ("--source", "--provider", "--claude", "--codex", "--copilot", "--copy", "--target"):
        assert flag in help_text, f"Expected {flag!r} in install --help output"


# ---------------------------------------------------------------------------
# uninstall --help
# ---------------------------------------------------------------------------


def test_uninstall_help_shows_all_flags() -> None:
    """clasr uninstall --help should list all documented flags."""
    result = subprocess.run(
        [sys.executable, "-m", "clasr.cli", "uninstall", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    help_text = result.stdout
    for flag in ("--provider", "--claude", "--codex", "--copilot", "--target"):
        assert flag in help_text, f"Expected {flag!r} in uninstall --help output"


# ---------------------------------------------------------------------------
# install validation
# ---------------------------------------------------------------------------


def test_install_no_platform_flag_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    """install with no platform flag should exit non-zero with a clear message."""
    with pytest.raises(SystemExit) as exc_info:
        main(["install", "--source", "/tmp/asr", "--provider", "test"])
    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert "claude" in captured.err.lower() or "platform" in captured.err.lower()


def test_install_no_provider_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    """install without --provider should exit non-zero with an error message."""
    with pytest.raises(SystemExit) as exc_info:
        main(["install", "--source", "/tmp/asr", "--claude"])
    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert "provider" in captured.err.lower()


def test_install_no_source_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    """install without --source should exit non-zero with an error message."""
    with pytest.raises(SystemExit) as exc_info:
        main(["install", "--provider", "test", "--claude"])
    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert "source" in captured.err.lower()


def test_install_nonexistent_source_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """install with a --source that does not exist should return exit code 1."""
    rc = main(["install", "--source", str(tmp_path / "does-not-exist"), "--provider", "test", "--claude"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "source" in captured.err.lower()


def test_install_valid_args_exits_zero(tmp_path: Path) -> None:
    """install with all required args and a valid source should exit 0."""
    asr = _build_asr_fixture(tmp_path)
    target = tmp_path / "project"
    target.mkdir()
    rc = main(["install", "--source", str(asr), "--provider", "test", "--claude", "--target", str(target)])
    assert rc == 0


# ---------------------------------------------------------------------------
# uninstall validation
# ---------------------------------------------------------------------------


def test_uninstall_no_platform_flag_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    """uninstall with no platform flag should exit non-zero with a clear message."""
    with pytest.raises(SystemExit) as exc_info:
        main(["uninstall", "--provider", "test"])
    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert "claude" in captured.err.lower() or "platform" in captured.err.lower()


def test_uninstall_no_provider_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    """uninstall without --provider should exit non-zero with an error message."""
    with pytest.raises(SystemExit) as exc_info:
        main(["uninstall", "--claude"])
    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert "provider" in captured.err.lower()


def test_uninstall_valid_args_exits_zero(tmp_path: Path) -> None:
    """uninstall with all required args (no manifest) exits 0 (idempotent)."""
    target = tmp_path / "project"
    target.mkdir()
    rc = main(["uninstall", "--provider", "test", "--claude", "--target", str(target)])
    assert rc == 0


# ---------------------------------------------------------------------------
# Integration: install end-to-end
# ---------------------------------------------------------------------------


def test_install_claude_end_to_end(tmp_path: Path) -> None:
    """install --claude should create a manifest and install skills/agents/rules."""
    asr = _build_asr_fixture(tmp_path)
    target = tmp_path / "project"
    target.mkdir()

    rc = main([
        "install",
        "--source", str(asr),
        "--provider", "smoke",
        "--claude",
        "--target", str(target),
    ])
    assert rc == 0

    # Manifest must exist.
    manifest_path = target / ".claude" / ".clasr-manifest" / "smoke.json"
    assert manifest_path.exists(), "Manifest not written"

    import json
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["provider"] == "smoke"
    assert data["platform"] == "claude"
    assert len(data["entries"]) > 0

    # Skills directory created.
    assert (target / ".claude" / "skills" / "foo" / "SKILL.md").exists()

    # Agents rendered.
    assert (target / ".claude" / "agents" / "bar.md").exists()

    # Rules rendered.
    assert (target / ".claude" / "rules" / "baz.md").exists()


def test_install_all_three(tmp_path: Path) -> None:
    """install --claude --codex --copilot should install to all three platforms."""
    asr = _build_asr_fixture(tmp_path)
    target = tmp_path / "project"
    target.mkdir()

    rc = main([
        "install",
        "--source", str(asr),
        "--provider", "smoke",
        "--claude",
        "--codex",
        "--copilot",
        "--target", str(target),
    ])
    assert rc == 0

    # Each platform writes its own manifest.
    assert (target / ".claude" / ".clasr-manifest" / "smoke.json").exists(), "Claude manifest missing"
    assert (target / ".codex" / ".clasr-manifest" / "smoke.json").exists(), "Codex manifest missing"
    assert (target / ".github" / ".clasr-manifest" / "smoke.json").exists(), "Copilot manifest missing"


def test_uninstall_after_install(tmp_path: Path) -> None:
    """Round-trip: install then uninstall should remove the manifest."""
    asr = _build_asr_fixture(tmp_path)
    target = tmp_path / "project"
    target.mkdir()

    rc_install = main([
        "install",
        "--source", str(asr),
        "--provider", "smoke",
        "--claude",
        "--target", str(target),
    ])
    assert rc_install == 0
    manifest_path = target / ".claude" / ".clasr-manifest" / "smoke.json"
    assert manifest_path.exists(), "Manifest should exist after install"

    rc_uninstall = main([
        "uninstall",
        "--provider", "smoke",
        "--claude",
        "--target", str(target),
    ])
    assert rc_uninstall == 0
    assert not manifest_path.exists(), "Manifest should be gone after uninstall"


def test_install_with_copy_flag(tmp_path: Path) -> None:
    """--copy flag should result in copied files rather than symlinks for skills."""
    asr = _build_asr_fixture(tmp_path)
    target = tmp_path / "project"
    target.mkdir()

    rc = main([
        "install",
        "--source", str(asr),
        "--provider", "smoke",
        "--claude",
        "--copy",
        "--target", str(target),
    ])
    assert rc == 0

    skill_path = target / ".claude" / "skills" / "foo" / "SKILL.md"
    assert skill_path.exists()
    # With --copy, it should be a regular file, not a symlink.
    assert not skill_path.is_symlink(), "Expected a copy, not a symlink"

    # Manifest records copy kind.
    import json
    manifest_path = target / ".claude" / ".clasr-manifest" / "smoke.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    skill_entry = next(
        (e for e in data["entries"] if "SKILL.md" in e.get("path", "")),
        None,
    )
    assert skill_entry is not None
    assert skill_entry["kind"] == "copy"


# ---------------------------------------------------------------------------
# platforms list
# ---------------------------------------------------------------------------


def test_platforms_list_prints_sorted_ids(capsys: pytest.CaptureFixture[str]) -> None:
    """clasr platforms list should print registered platform IDs sorted, one per line."""
    rc = main(["platforms", "list"])
    captured = capsys.readouterr()
    assert rc == 0
    lines = captured.out.splitlines()
    assert lines == sorted(lines), "Platform IDs should be sorted"
    assert len(lines) > 0, "Should list at least one platform"
    # cursor is registered in this sprint
    assert "cursor" in lines
    # verify the expected set of currently registered platforms
    assert "claude" in lines
    assert "codex" in lines
    assert "copilot" in lines


def test_platforms_list_via_subprocess() -> None:
    """clasr platforms list should work end-to-end via subprocess and exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "clasr.cli", "platforms", "list"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert "cursor" in lines
    assert lines == sorted(lines)


def test_platforms_no_subcommand_prints_help_exits_zero() -> None:
    """clasr platforms (no subcommand) should print help and exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "clasr.cli", "platforms"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "list" in result.stdout


# ---------------------------------------------------------------------------
# No imports from clasi (static check)
# ---------------------------------------------------------------------------


def test_no_imports_from_clasi() -> None:
    """clasr/cli.py must not import anything from the clasi package."""
    import importlib.resources
    package_ref = importlib.resources.files("clasr")
    cli_path = package_ref / "cli.py"
    source = cli_path.read_text(encoding="utf-8")
    assert "from clasi" not in source, "clasr/cli.py must not import from clasi"
    assert "import clasi" not in source, "clasr/cli.py must not import clasi"
