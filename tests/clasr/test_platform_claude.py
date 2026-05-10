"""
tests/clasr/test_platform_claude.py

Tests for clasr.platforms.claude — Claude platform installer.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Generator

import pytest

from clasr.platforms.claude import ClaudeIntegration

# Convenience aliases so test bodies read naturally without rewriting every call.
_integration = ClaudeIntegration()
install = _integration.install
uninstall = _integration.uninstall


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_asr(base: Path) -> Path:
    """Create a minimal asr/ source tree under *base* and return its path."""
    src = base / "asr"

    # AGENTS.md
    (src).mkdir(parents=True, exist_ok=True)
    (src / "AGENTS.md").write_text(
        "Use clasr to manage multi-platform AI agent configurations.",
        encoding="utf-8",
    )

    # skills/my-skill/SKILL.md
    skill_dir = src / "skills" / "my-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# My Skill\nDoes stuff.", encoding="utf-8")

    # agents/code-review.md (union frontmatter)
    agents_dir = src / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "code-review.md").write_text(
        "---\n"
        "name: code-review\n"
        "description: Review a PR\n"
        "claude:\n"
        "  tools: [Read, Bash]\n"
        "copilot:\n"
        "  applyTo: '**/*.ts'\n"
        "---\n\n"
        "Review the pull request carefully.\n",
        encoding="utf-8",
    )

    # rules/security.md (union frontmatter)
    rules_dir = src / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "security.md").write_text(
        "---\n"
        "description: Security rules\n"
        "claude: {}\n"
        "---\n\n"
        "Never expose secrets.\n",
        encoding="utf-8",
    )

    # claude/ passthrough
    claude_pass = src / "claude"
    claude_pass.mkdir(parents=True, exist_ok=True)
    (claude_pass / "settings.json").write_text(
        json.dumps({"model": "sonnet", "permissions": ["read"]}),
        encoding="utf-8",
    )

    return src


def _dir_hash(path: Path) -> str:
    """Return a deterministic hash of all file contents under *path*."""
    h = hashlib.sha256()
    for f in sorted(path.rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(path)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> dict:
    """Return a dict with 'source', 'target', 'provider' keys."""
    source = _make_asr(tmp_path)
    target = tmp_path / "project"
    target.mkdir()
    return {"source": source, "target": target, "provider": "testprovider"}


# ---------------------------------------------------------------------------
# install — skills
# ---------------------------------------------------------------------------


def test_install_creates_skill_symlinks(workspace: dict) -> None:
    install(**workspace)
    alias = workspace["target"] / ".claude" / "skills" / "my-skill" / "SKILL.md"
    assert alias.exists()
    assert alias.is_symlink()
    # Symlink target must be absolute.
    assert os.path.isabs(os.readlink(alias))


def test_install_skill_copy_mode(workspace: dict) -> None:
    workspace["copy"] = True
    install(**workspace)
    alias = workspace["target"] / ".claude" / "skills" / "my-skill" / "SKILL.md"
    assert alias.exists()
    assert not alias.is_symlink()


# ---------------------------------------------------------------------------
# install — agents
# ---------------------------------------------------------------------------


def test_install_renders_agents(workspace: dict) -> None:
    install(**workspace)
    out = workspace["target"] / ".claude" / "agents" / "code-review.md"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    # Should have projected frontmatter (claude keys merged in).
    assert "tools:" in text
    # copilot-specific key should NOT appear.
    assert "applyTo" not in text


# ---------------------------------------------------------------------------
# install — rules
# ---------------------------------------------------------------------------


def test_install_renders_rules(workspace: dict) -> None:
    install(**workspace)
    out = workspace["target"] / ".claude" / "rules" / "security.md"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Never expose secrets" in text


# ---------------------------------------------------------------------------
# install — passthrough (JSON)
# ---------------------------------------------------------------------------


def test_install_passthrough_json(workspace: dict) -> None:
    install(**workspace)
    settings = workspace["target"] / ".claude" / "settings.json"
    assert settings.exists()
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["model"] == "sonnet"


def test_install_json_merged(tmp_path: Path) -> None:
    """When dest settings.json already exists (another provider), merge."""
    source = _make_asr(tmp_path)
    target = tmp_path / "project"
    target.mkdir()
    claude_dir = target / ".claude"
    claude_dir.mkdir()

    # Pre-create a settings.json from "another provider".
    existing_settings = {"model": "haiku", "debug": True}
    (claude_dir / "settings.json").write_text(
        json.dumps(existing_settings), encoding="utf-8"
    )

    # Write a fake manifest for the other provider so collision detection works.
    other_manifest = {
        "version": 1,
        "provider": "otherprovider",
        "platform": "claude",
        "source": "/fake",
        "entries": [
            {"path": ".claude/settings.json", "kind": "copy"},
        ],
    }
    manifest_dir = claude_dir / ".clasr-manifest"
    manifest_dir.mkdir()
    (manifest_dir / "otherprovider.json").write_text(
        json.dumps(other_manifest), encoding="utf-8"
    )

    install(source, target, provider="testprovider")

    settings = claude_dir / "settings.json"
    assert settings.exists()
    data = json.loads(settings.read_text(encoding="utf-8"))

    # Both providers' keys should be present.
    assert "model" in data  # from incoming (testprovider wins)
    assert "debug" in data  # from existing (otherprovider)

    # Manifest should record json-merged.
    mf_path = manifest_dir / "testprovider.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))
    json_merged_entries = [e for e in mf["entries"] if e["kind"] == "json-merged"]
    assert len(json_merged_entries) == 1
    assert "model" in json_merged_entries[0]["keys"]


def test_install_json_merged_uninstall(tmp_path: Path) -> None:
    """After merging two providers, uninstalling one should leave the other's keys."""
    source = _make_asr(tmp_path)
    target = tmp_path / "project"
    target.mkdir()
    claude_dir = target / ".claude"
    claude_dir.mkdir()

    # Pre-install "otherprovider" with its own settings.
    other_settings = {"debug": True, "theme": "dark"}
    (claude_dir / "settings.json").write_text(
        json.dumps(other_settings), encoding="utf-8"
    )
    manifest_dir = claude_dir / ".clasr-manifest"
    manifest_dir.mkdir()
    (manifest_dir / "otherprovider.json").write_text(
        json.dumps({
            "version": 1,
            "provider": "otherprovider",
            "platform": "claude",
            "source": "/fake",
            "entries": [{"path": ".claude/settings.json", "kind": "copy"}],
        }),
        encoding="utf-8",
    )

    # Install testprovider — merges its keys.
    install(source, target, provider="testprovider")

    # After install: both providers' keys are present.
    data = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    assert "model" in data
    assert "debug" in data

    # Uninstall testprovider — should only remove its keys.
    uninstall(target, provider="testprovider")

    data_after = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    assert "model" not in data_after      # testprovider contributed this
    assert "debug" in data_after          # otherprovider owns this — untouched

    # testprovider manifest should be gone.
    assert not (manifest_dir / "testprovider.json").exists()


def test_install_json_merged_uninstall_empty_deletes_file(tmp_path: Path) -> None:
    """When uninstalling leaves an empty JSON, delete the file."""
    source = _make_asr(tmp_path)
    target = tmp_path / "project"
    target.mkdir()

    # Install provider — no prior settings.json, so kind=copy.
    install(source, target, provider="testprovider")

    # settings.json should exist.
    settings = target / ".claude" / "settings.json"
    assert settings.exists()

    # Replace the manifest entry with json-merged so uninstall pops all keys.
    mf_path = target / ".claude" / ".clasr-manifest" / "testprovider.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))
    for e in mf["entries"]:
        if e["path"] == ".claude/settings.json":
            e["kind"] = "json-merged"
            e["keys"] = list(json.loads(settings.read_text(encoding="utf-8")).keys())
    mf_path.write_text(json.dumps(mf), encoding="utf-8")

    uninstall(target, provider="testprovider")

    # File should be gone (all keys removed → empty).
    assert not settings.exists()


# ---------------------------------------------------------------------------
# install — non-JSON collision
# ---------------------------------------------------------------------------


def test_install_nonjson_collision_raises(tmp_path: Path) -> None:
    """Non-JSON passthrough: collision with another provider should raise."""
    source = _make_asr(tmp_path)

    # Add a non-JSON passthrough file.
    (source / "claude" / "custom.md").write_text("# Custom", encoding="utf-8")

    target = tmp_path / "project"
    target.mkdir()
    claude_dir = target / ".claude"
    claude_dir.mkdir()

    # Pre-create the file as if another provider owns it.
    (claude_dir / "custom.md").write_text("# Owned by other", encoding="utf-8")

    manifest_dir = claude_dir / ".clasr-manifest"
    manifest_dir.mkdir()
    (manifest_dir / "rivalprovider.json").write_text(
        json.dumps({
            "version": 1,
            "provider": "rivalprovider",
            "platform": "claude",
            "source": "/fake",
            "entries": [{"path": ".claude/custom.md", "kind": "copy"}],
        }),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError) as exc_info:
        install(source, target, provider="testprovider")

    msg = str(exc_info.value)
    assert "rivalprovider" in msg
    assert "testprovider" in msg


# ---------------------------------------------------------------------------
# install — marker blocks
# ---------------------------------------------------------------------------


def test_install_writes_marker_blocks(workspace: dict) -> None:
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]
    block_begin = f"<!-- BEGIN clasr:{provider} -->"

    for filename in ("AGENTS.md", "CLAUDE.md"):
        dest = target / filename
        assert dest.exists(), f"{filename} not created"
        text = dest.read_text(encoding="utf-8")
        assert block_begin in text, f"{filename} missing marker block"


def test_install_marker_block_content(workspace: dict) -> None:
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    for filename in ("AGENTS.md", "CLAUDE.md"):
        text = (target / filename).read_text(encoding="utf-8")
        # Content from source/AGENTS.md should be inside the block.
        assert "clasr" in text.lower() or "multi-platform" in text.lower() or \
            "Use clasr" in text


# ---------------------------------------------------------------------------
# install — manifest
# ---------------------------------------------------------------------------


def test_install_writes_manifest(workspace: dict) -> None:
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]
    mf_path = target / ".claude" / ".clasr-manifest" / f"{provider}.json"
    assert mf_path.exists()
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    assert mf["version"] == 1
    assert mf["provider"] == provider
    assert mf["platform"] == "claude"
    assert isinstance(mf["entries"], list)
    assert len(mf["entries"]) > 0


def test_install_manifest_entry_paths_are_relative(workspace: dict) -> None:
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]
    mf_path = target / ".claude" / ".clasr-manifest" / f"{provider}.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    for entry in mf["entries"]:
        path = entry["path"]
        assert not path.startswith("/"), f"Manifest path is absolute: {path}"


def test_install_manifest_symlink_target_is_absolute(workspace: dict) -> None:
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]
    mf_path = target / ".claude" / ".clasr-manifest" / f"{provider}.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    for entry in mf["entries"]:
        if entry["kind"] == "symlink":
            assert os.path.isabs(entry["target"]), \
                f"Symlink target not absolute: {entry['target']}"


# ---------------------------------------------------------------------------
# uninstall — full cleanup
# ---------------------------------------------------------------------------


def test_uninstall_removes_all_entries(workspace: dict) -> None:
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    # Collect installed files from manifest.
    mf_path = target / ".claude" / ".clasr-manifest" / f"{provider}.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    uninstall(target, provider)

    # Manifest file should be gone.
    assert not mf_path.exists()

    # All entries should be removed.
    for entry in mf["entries"]:
        kind = entry["kind"]
        path_rel = entry["path"]
        full_path = target / path_rel

        if kind in ("symlink", "copy", "rendered"):
            assert not full_path.exists(), f"File still exists after uninstall: {path_rel}"
        elif kind == "marker-block":
            if full_path.exists():
                text = full_path.read_text(encoding="utf-8")
                block_begin = f"<!-- BEGIN clasr:{provider} -->"
                assert block_begin not in text, \
                    f"Marker block still present in {path_rel}"


def test_uninstall_idempotent_no_manifest(tmp_path: Path) -> None:
    """Uninstall with no manifest should not raise."""
    target = tmp_path / "project"
    target.mkdir()
    # Should not raise.
    uninstall(target, provider="nonexistent")


# ---------------------------------------------------------------------------
# source directory immutability
# ---------------------------------------------------------------------------


def test_source_dir_immutable(workspace: dict) -> None:
    source = workspace["source"]
    hash_before = _dir_hash(source)
    install(**workspace)
    hash_after = _dir_hash(source)
    assert hash_before == hash_after, "install() modified the source directory"


# ---------------------------------------------------------------------------
# no clasi imports
# ---------------------------------------------------------------------------


def test_no_clasi_imports() -> None:
    """Verify clasr.platforms.claude has no 'from clasi' or 'import clasi' imports."""
    module_path = Path(__file__).parent.parent.parent / "clasr" / "platforms" / "claude.py"
    source = module_path.read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        assert not (stripped.startswith("from clasi") or stripped.startswith("import clasi")), \
            f"Found clasi import: {line!r}"
