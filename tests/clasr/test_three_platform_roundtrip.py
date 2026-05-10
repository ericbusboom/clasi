"""
tests/clasr/test_three_platform_roundtrip.py

Integration test: installs all three platforms (Claude, Codex, Copilot) from a
single fixture asr/ directory into a shared target, verifies the expected outputs,
then uninstalls Claude only and confirms Codex and Copilot are still intact.

Design notes:
    - All three platforms share the same provider name ("testprov") in this test.
      Claude and Codex both write to root AGENTS.md with the same marker name, so
      the last writer (Codex) wins. After Claude uninstall, the AGENTS.md block is
      stripped (it was written by the same provider name, so Claude's uninstall
      strips it). Block-survival with different providers is covered in test 013
      (multi-tenant test).
    - Source dir immutability: a SHA-256 hash of all file contents is taken before
      any installs and compared after the full install+uninstall cycle.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from clasr.platforms.claude import ClaudeIntegration
from clasr.platforms.codex import CodexIntegration
from clasr.platforms.copilot import CopilotIntegration

# Small namespaces so existing test bodies don't need rewriting.
class _Platform:
    def __init__(self, inst):
        self.install = inst.install
        self.uninstall = inst.uninstall

claude_platform = _Platform(ClaudeIntegration())
codex_platform = _Platform(CodexIntegration())
copilot_platform = _Platform(CopilotIntegration())

from tests.clasr.conftest import make_asr_dir


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dir_hash(path: Path) -> str:
    """Return a deterministic SHA-256 hash of all file contents under *path*."""
    h = hashlib.sha256()
    for f in sorted(path.rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(path)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


PROVIDER = "testprov"
SKILL = "foo"


@pytest.fixture
def workspace(tmp_path: Path) -> dict:
    """Return source, target, and provider for three-platform roundtrip tests."""
    source = make_asr_dir(tmp_path, provider=PROVIDER, skill_names=(SKILL,))
    target = tmp_path / "project"
    target.mkdir()
    return {"source": source, "target": target, "provider": PROVIDER}


# ---------------------------------------------------------------------------
# Helper: install all three platforms
# ---------------------------------------------------------------------------


def _install_all(workspace: dict) -> None:
    source = workspace["source"]
    target = workspace["target"]
    provider = workspace["provider"]
    claude_platform.install(source=source, target=target, provider=provider)
    codex_platform.install(source=source, target=target, provider=provider)
    copilot_platform.install(source=source, target=target, provider=provider)


# ---------------------------------------------------------------------------
# Test: all three manifests exist after full install
# ---------------------------------------------------------------------------


def test_all_manifests_exist(workspace: dict) -> None:
    """After installing all three platforms, each has a manifest file."""
    _install_all(workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    claude_mf = target / ".claude" / ".clasr-manifest" / f"{provider}.json"
    codex_mf = target / ".codex" / ".clasr-manifest" / f"{provider}.json"
    copilot_mf = target / ".github" / ".clasr-manifest" / f"{provider}.json"

    assert claude_mf.exists(), "Claude manifest missing"
    assert codex_mf.exists(), "Codex manifest missing"
    assert copilot_mf.exists(), "Copilot manifest missing"


# ---------------------------------------------------------------------------
# Test: marker blocks
# ---------------------------------------------------------------------------


def test_agents_md_has_marker_block(workspace: dict) -> None:
    """AGENTS.md contains exactly one clasr:testprov marker block after all installs.

    Both Claude and Codex write to AGENTS.md with the same provider name, so the
    second writer (Codex) overwrites the first. Exactly one BEGIN marker is expected.
    """
    _install_all(workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    agents_md = target / "AGENTS.md"
    assert agents_md.exists(), "AGENTS.md was not created"

    text = agents_md.read_text(encoding="utf-8")
    block_begin = f"<!-- BEGIN clasr:{provider} -->"
    count = text.count(block_begin)
    assert count == 1, (
        f"Expected exactly 1 '{block_begin}' in AGENTS.md, found {count}"
    )


def test_claude_md_has_marker_block(workspace: dict) -> None:
    """CLAUDE.md contains the named marker block (written by Claude only)."""
    _install_all(workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    claude_md = target / "CLAUDE.md"
    assert claude_md.exists(), "CLAUDE.md was not created"

    text = claude_md.read_text(encoding="utf-8")
    block_begin = f"<!-- BEGIN clasr:{provider} -->"
    assert block_begin in text, "CLAUDE.md missing named marker block"


def test_copilot_instructions_has_marker_block(workspace: dict) -> None:
    """.github/copilot-instructions.md contains the named marker block."""
    _install_all(workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    copilot_instr = target / ".github" / "copilot-instructions.md"
    assert copilot_instr.exists(), ".github/copilot-instructions.md was not created"

    text = copilot_instr.read_text(encoding="utf-8")
    block_begin = f"<!-- BEGIN clasr:{provider} -->"
    assert block_begin in text, ".github/copilot-instructions.md missing named marker block"


# ---------------------------------------------------------------------------
# Test: skill symlinks
# ---------------------------------------------------------------------------


def test_claude_skill_symlinks(workspace: dict) -> None:
    """After install, .claude/skills/<name>/SKILL.md exists as a symlink."""
    _install_all(workspace)
    target = workspace["target"]

    alias = target / ".claude" / "skills" / SKILL / "SKILL.md"
    assert alias.exists(), f".claude/skills/{SKILL}/SKILL.md missing"
    assert alias.is_symlink(), f".claude/skills/{SKILL}/SKILL.md is not a symlink"
    assert os.path.isabs(os.readlink(alias)), "Claude skill symlink target is not absolute"


def test_codex_skill_symlinks(workspace: dict) -> None:
    """After install, .agents/skills/<name>/SKILL.md exists as a symlink (Codex)."""
    _install_all(workspace)
    target = workspace["target"]

    alias = target / ".agents" / "skills" / SKILL / "SKILL.md"
    assert alias.exists(), f".agents/skills/{SKILL}/SKILL.md missing"
    assert alias.is_symlink(), f".agents/skills/{SKILL}/SKILL.md is not a symlink"
    assert os.path.isabs(os.readlink(alias)), "Codex skill symlink target is not absolute"


def test_copilot_github_skills_symlink(workspace: dict) -> None:
    """After install, .github/skills is a symlink to .agents/skills (Copilot)."""
    _install_all(workspace)
    target = workspace["target"]

    github_skills = target / ".github" / "skills"
    assert github_skills.exists(), ".github/skills missing"
    assert github_skills.is_symlink(), ".github/skills is not a symlink"


# ---------------------------------------------------------------------------
# Test: manifest validity
# ---------------------------------------------------------------------------


def test_manifests_are_valid_json(workspace: dict) -> None:
    """All three manifests parse as valid JSON with required fields."""
    _install_all(workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    manifest_paths = [
        target / ".claude" / ".clasr-manifest" / f"{provider}.json",
        target / ".codex" / ".clasr-manifest" / f"{provider}.json",
        target / ".github" / ".clasr-manifest" / f"{provider}.json",
    ]
    expected_platforms = ["claude", "codex", "copilot"]

    for mf_path, expected_platform in zip(manifest_paths, expected_platforms):
        mf = json.loads(mf_path.read_text(encoding="utf-8"))
        assert mf["version"] == 1
        assert mf["provider"] == provider
        assert mf["platform"] == expected_platform
        assert isinstance(mf["entries"], list)
        assert len(mf["entries"]) > 0


# ---------------------------------------------------------------------------
# Test: uninstall Claude only — Codex and Copilot survive
# ---------------------------------------------------------------------------


def test_uninstall_claude_leaves_codex_manifest(workspace: dict) -> None:
    """After uninstalling Claude, the Codex manifest still exists."""
    _install_all(workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    claude_platform.uninstall(target=target, provider=provider)

    codex_mf = target / ".codex" / ".clasr-manifest" / f"{provider}.json"
    assert codex_mf.exists(), "Codex manifest was removed when only Claude was uninstalled"


def test_uninstall_claude_leaves_copilot_manifest(workspace: dict) -> None:
    """After uninstalling Claude, the Copilot manifest still exists."""
    _install_all(workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    claude_platform.uninstall(target=target, provider=provider)

    copilot_mf = target / ".github" / ".clasr-manifest" / f"{provider}.json"
    assert copilot_mf.exists(), "Copilot manifest was removed when only Claude was uninstalled"


def test_uninstall_claude_manifest_gone(workspace: dict) -> None:
    """After uninstalling Claude, the Claude manifest is deleted."""
    _install_all(workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    claude_mf = target / ".claude" / ".clasr-manifest" / f"{provider}.json"
    assert claude_mf.exists()

    claude_platform.uninstall(target=target, provider=provider)

    assert not claude_mf.exists(), "Claude manifest was not removed after uninstall"


def test_uninstall_claude_codex_files_intact(workspace: dict) -> None:
    """After uninstalling Claude, Codex files (.codex/, .agents/) are still on disk."""
    _install_all(workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    # Read Codex manifest before uninstall to know which files were installed.
    codex_mf_path = target / ".codex" / ".clasr-manifest" / f"{provider}.json"
    codex_mf = json.loads(codex_mf_path.read_text(encoding="utf-8"))

    claude_platform.uninstall(target=target, provider=provider)

    # Verify Codex-specific files are still present.
    for entry in codex_mf["entries"]:
        if entry["kind"] in ("symlink", "copy", "rendered"):
            full_path = target / entry["path"]
            assert full_path.exists(), (
                f"Codex file missing after Claude uninstall: {entry['path']}"
            )


def test_uninstall_claude_copilot_files_intact(workspace: dict) -> None:
    """After uninstalling Claude, Copilot files (.github/agents/, etc.) are still on disk."""
    _install_all(workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    # Read Copilot manifest before uninstall to know which files were installed.
    copilot_mf_path = target / ".github" / ".clasr-manifest" / f"{provider}.json"
    copilot_mf = json.loads(copilot_mf_path.read_text(encoding="utf-8"))

    claude_platform.uninstall(target=target, provider=provider)

    # Verify Copilot-specific files are still present (skip marker-block entries
    # as their file may be shared with Claude; we only check hard file entries).
    for entry in copilot_mf["entries"]:
        if entry["kind"] in ("symlink", "copy", "rendered"):
            full_path = target / entry["path"]
            assert full_path.exists(), (
                f"Copilot file missing after Claude uninstall: {entry['path']}"
            )


def test_uninstall_claude_copilot_instructions_intact(workspace: dict) -> None:
    """.github/copilot-instructions.md still contains the Copilot marker block after
    Claude uninstall.

    Copilot writes its block to .github/copilot-instructions.md. Claude does NOT
    write to that file — it writes to CLAUDE.md and AGENTS.md. So uninstalling
    Claude must not affect .github/copilot-instructions.md.
    """
    _install_all(workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    claude_platform.uninstall(target=target, provider=provider)

    copilot_instr = target / ".github" / "copilot-instructions.md"
    assert copilot_instr.exists(), (
        ".github/copilot-instructions.md was removed when only Claude was uninstalled"
    )
    text = copilot_instr.read_text(encoding="utf-8")
    block_begin = f"<!-- BEGIN clasr:{provider} -->"
    assert block_begin in text, (
        ".github/copilot-instructions.md marker block was stripped after Claude uninstall"
    )


def test_uninstall_claude_removes_claude_md(workspace: dict) -> None:
    """After uninstalling Claude, CLAUDE.md marker block is stripped."""
    _install_all(workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    claude_md = target / "CLAUDE.md"
    text_before = claude_md.read_text(encoding="utf-8")
    block_begin = f"<!-- BEGIN clasr:{provider} -->"
    assert block_begin in text_before

    claude_platform.uninstall(target=target, provider=provider)

    if claude_md.exists():
        text_after = claude_md.read_text(encoding="utf-8")
        assert block_begin not in text_after, "CLAUDE.md block not stripped after Claude uninstall"


# ---------------------------------------------------------------------------
# Test: source directory immutability
# ---------------------------------------------------------------------------


def test_source_dir_immutable_after_full_cycle(workspace: dict) -> None:
    """Source asr/ dir is byte-identical before and after the full install+uninstall cycle."""
    source = workspace["source"]
    hash_before = _dir_hash(source)

    _install_all(workspace)

    target = workspace["target"]
    provider = workspace["provider"]
    claude_platform.uninstall(target=target, provider=provider)

    hash_after = _dir_hash(source)
    assert hash_before == hash_after, (
        "Source asr/ directory was modified during the install+uninstall cycle"
    )
