"""
tests/clasr/test_platform_codex.py

Tests for clasr.platforms.codex — Codex platform installer.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from clasr.platforms.codex import CodexIntegration

# Convenience aliases so test bodies read naturally without rewriting every call.
_integration = CodexIntegration()
install = _integration.install
uninstall = _integration.uninstall


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_asr(base: Path) -> Path:
    """Create a minimal asr/ source tree under *base* and return its path."""
    src = base / "asr"

    # AGENTS.md
    src.mkdir(parents=True, exist_ok=True)
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
        "codex: {}\n"
        "---\n\n"
        "Review the pull request carefully.\n",
        encoding="utf-8",
    )

    # rules/security.md — unscoped rule (no applyTo/paths)
    rules_dir = src / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "security.md").write_text(
        "---\n"
        "description: Security rules\n"
        "codex: {}\n"
        "---\n\n"
        "Never expose secrets.\n",
        encoding="utf-8",
    )

    # codex/ passthrough
    codex_pass = src / "codex"
    codex_pass.mkdir(parents=True, exist_ok=True)
    (codex_pass / "config.json").write_text(
        json.dumps({"model": "codex-latest", "permissions": ["read"]}),
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
# install — agents
# ---------------------------------------------------------------------------


def test_install_creates_agent_files(workspace: dict) -> None:
    install(**workspace)
    out = workspace["target"] / ".codex" / "agents" / "code-review.md"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    # Should have projected frontmatter; codex platform key merged in.
    assert "code-review" in text
    # claude-specific tool should NOT appear in codex output.
    assert "Read" not in text or "tools" not in text


# ---------------------------------------------------------------------------
# install — skills
# ---------------------------------------------------------------------------


def test_install_skills(workspace: dict) -> None:
    """Skills are symlinked to .agents/skills/<n>/SKILL.md."""
    install(**workspace)
    alias = workspace["target"] / ".agents" / "skills" / "my-skill" / "SKILL.md"
    assert alias.exists()
    assert alias.is_symlink()
    assert os.path.isabs(os.readlink(alias))


def test_install_skill_copy_mode(workspace: dict) -> None:
    workspace["copy"] = True
    install(**workspace)
    alias = workspace["target"] / ".agents" / "skills" / "my-skill" / "SKILL.md"
    assert alias.exists()
    assert not alias.is_symlink()


# ---------------------------------------------------------------------------
# install — rules (scoped)
# ---------------------------------------------------------------------------


def test_install_scoped_rule_creates_nested_agents_md(tmp_path: Path) -> None:
    """applyTo: 'docs/clasi/**' → target/docs/clasi/AGENTS.md with rule body."""
    src = _make_asr(tmp_path)
    # Add a scoped rule.
    (src / "rules" / "clasi-rules.md").write_text(
        "---\n"
        "description: Clasi-specific rules\n"
        "codex:\n"
        "  applyTo: 'docs/clasi/**'\n"
        "---\n\n"
        "Always follow CLASI process.\n",
        encoding="utf-8",
    )

    target = tmp_path / "project"
    target.mkdir()
    install(source=src, target=target, provider="testprovider")

    nested = target / "docs" / "clasi" / "AGENTS.md"
    assert nested.exists(), "Scoped rule should create docs/clasi/AGENTS.md"
    text = nested.read_text(encoding="utf-8")
    assert "Always follow CLASI process" in text


def test_install_scoped_rule_manifest_entry(tmp_path: Path) -> None:
    """Scoped rule creates a 'rendered' manifest entry with correct path."""
    src = _make_asr(tmp_path)
    (src / "rules" / "clasi-rules.md").write_text(
        "---\n"
        "codex:\n"
        "  applyTo: 'docs/clasi/**'\n"
        "---\n\n"
        "Rule body here.\n",
        encoding="utf-8",
    )

    target = tmp_path / "project"
    target.mkdir()
    install(source=src, target=target, provider="testprovider")

    mf_path = target / ".codex" / ".clasr-manifest" / "testprovider.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    rendered_entries = [e for e in mf["entries"] if e["kind"] == "rendered" and "clasi" in e["path"]]
    assert len(rendered_entries) >= 1
    paths = [e["path"] for e in rendered_entries]
    assert any("docs/clasi/AGENTS.md" in p for p in paths)


# ---------------------------------------------------------------------------
# install — rules (unscoped)
# ---------------------------------------------------------------------------


def test_install_unscoped_rule_in_root_agents_md(workspace: dict) -> None:
    """Unscoped rule body appears inside the root AGENTS.md marker block."""
    install(**workspace)
    agents_md = workspace["target"] / "AGENTS.md"
    assert agents_md.exists()
    text = agents_md.read_text(encoding="utf-8")
    assert "Never expose secrets" in text
    # Verify it is inside a marker block.
    assert "<!-- BEGIN clasr:testprovider -->" in text


def test_install_unscoped_rule_not_separate_file(workspace: dict) -> None:
    """Unscoped rule should NOT create a separate file in .codex/rules/."""
    install(**workspace)
    rules_dir = workspace["target"] / ".codex" / "rules"
    # Rules directory should not exist for Codex (rules are not written there).
    if rules_dir.exists():
        rule_files = list(rules_dir.rglob("*.md"))
        assert len(rule_files) == 0, "Codex should not write rule files to .codex/rules/"


# ---------------------------------------------------------------------------
# install — marker block
# ---------------------------------------------------------------------------


def test_install_writes_agents_md_block(workspace: dict) -> None:
    """Root AGENTS.md gets a named marker block (not CLAUDE.md)."""
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]
    block_begin = f"<!-- BEGIN clasr:{provider} -->"

    agents_md = target / "AGENTS.md"
    assert agents_md.exists(), "AGENTS.md not created"
    text = agents_md.read_text(encoding="utf-8")
    assert block_begin in text, "AGENTS.md missing marker block"


def test_install_no_claude_md_block(workspace: dict) -> None:
    """Codex installer must NOT write CLAUDE.md marker block."""
    install(**workspace)
    claude_md = workspace["target"] / "CLAUDE.md"
    # CLAUDE.md should not be created by codex installer.
    assert not claude_md.exists(), "Codex should not create CLAUDE.md"


def test_install_marker_block_content(workspace: dict) -> None:
    """source/AGENTS.md content is inside the AGENTS.md marker block."""
    install(**workspace)
    target = workspace["target"]
    text = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "Use clasr" in text or "multi-platform" in text.lower()


# ---------------------------------------------------------------------------
# install — passthrough (JSON)
# ---------------------------------------------------------------------------


def test_install_passthrough_json(workspace: dict) -> None:
    install(**workspace)
    config = workspace["target"] / ".codex" / "config.json"
    assert config.exists()
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["model"] == "codex-latest"


def test_install_json_merged(tmp_path: Path) -> None:
    """When dest config.json already exists (another provider), merge."""
    source = _make_asr(tmp_path)
    target = tmp_path / "project"
    target.mkdir()
    codex_dir = target / ".codex"
    codex_dir.mkdir()

    # Pre-create a config.json from "another provider".
    existing_config = {"model": "gpt4", "debug": True}
    (codex_dir / "config.json").write_text(
        json.dumps(existing_config), encoding="utf-8"
    )

    # Write a fake manifest for the other provider.
    other_manifest = {
        "version": 1,
        "provider": "otherprovider",
        "platform": "codex",
        "source": "/fake",
        "entries": [
            {"path": ".codex/config.json", "kind": "copy"},
        ],
    }
    manifest_dir = codex_dir / ".clasr-manifest"
    manifest_dir.mkdir()
    (manifest_dir / "otherprovider.json").write_text(
        json.dumps(other_manifest), encoding="utf-8"
    )

    install(source, target, provider="testprovider")

    config = codex_dir / "config.json"
    assert config.exists()
    data = json.loads(config.read_text(encoding="utf-8"))

    # Both providers' keys should be present.
    assert "model" in data
    assert "debug" in data

    # Manifest should record json-merged.
    mf_path = manifest_dir / "testprovider.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))
    json_merged_entries = [e for e in mf["entries"] if e["kind"] == "json-merged"]
    assert len(json_merged_entries) == 1
    assert "model" in json_merged_entries[0]["keys"]


def test_install_json_merged_uninstall(tmp_path: Path) -> None:
    """After merging two providers, uninstalling one leaves the other's keys."""
    source = _make_asr(tmp_path)
    target = tmp_path / "project"
    target.mkdir()
    codex_dir = target / ".codex"
    codex_dir.mkdir()

    # Pre-install "otherprovider" with its own config.
    other_config = {"debug": True, "theme": "dark"}
    (codex_dir / "config.json").write_text(
        json.dumps(other_config), encoding="utf-8"
    )
    manifest_dir = codex_dir / ".clasr-manifest"
    manifest_dir.mkdir()
    (manifest_dir / "otherprovider.json").write_text(
        json.dumps({
            "version": 1,
            "provider": "otherprovider",
            "platform": "codex",
            "source": "/fake",
            "entries": [{"path": ".codex/config.json", "kind": "copy"}],
        }),
        encoding="utf-8",
    )

    install(source, target, provider="testprovider")

    data = json.loads((codex_dir / "config.json").read_text(encoding="utf-8"))
    assert "model" in data
    assert "debug" in data

    uninstall(target, provider="testprovider")

    data_after = json.loads((codex_dir / "config.json").read_text(encoding="utf-8"))
    assert "model" not in data_after   # testprovider contributed this
    assert "debug" in data_after       # otherprovider owns this — untouched

    assert not (manifest_dir / "testprovider.json").exists()


def test_install_json_merged_uninstall_empty_deletes_file(tmp_path: Path) -> None:
    """When uninstalling removes all keys, delete the file."""
    source = _make_asr(tmp_path)
    target = tmp_path / "project"
    target.mkdir()

    install(source, target, provider="testprovider")

    config = target / ".codex" / "config.json"
    assert config.exists()

    # Replace the manifest entry with json-merged so uninstall pops all keys.
    mf_path = target / ".codex" / ".clasr-manifest" / "testprovider.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))
    for e in mf["entries"]:
        if e["path"] == ".codex/config.json":
            e["kind"] = "json-merged"
            e["keys"] = list(json.loads(config.read_text(encoding="utf-8")).keys())
    mf_path.write_text(json.dumps(mf), encoding="utf-8")

    uninstall(target, provider="testprovider")

    assert not config.exists()


# ---------------------------------------------------------------------------
# install — non-JSON collision
# ---------------------------------------------------------------------------


def test_install_nonjson_collision_raises(tmp_path: Path) -> None:
    """Non-JSON passthrough: collision with another provider raises."""
    source = _make_asr(tmp_path)

    # Add a non-JSON passthrough file.
    (source / "codex" / "custom.md").write_text("# Custom", encoding="utf-8")

    target = tmp_path / "project"
    target.mkdir()
    codex_dir = target / ".codex"
    codex_dir.mkdir()

    # Pre-create the file as if another provider owns it.
    (codex_dir / "custom.md").write_text("# Owned by other", encoding="utf-8")

    manifest_dir = codex_dir / ".clasr-manifest"
    manifest_dir.mkdir()
    (manifest_dir / "rivalprovider.json").write_text(
        json.dumps({
            "version": 1,
            "provider": "rivalprovider",
            "platform": "codex",
            "source": "/fake",
            "entries": [{"path": ".codex/custom.md", "kind": "copy"}],
        }),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError) as exc_info:
        install(source, target, provider="testprovider")

    msg = str(exc_info.value)
    assert "rivalprovider" in msg
    assert "testprovider" in msg


# ---------------------------------------------------------------------------
# install — manifest
# ---------------------------------------------------------------------------


def test_install_writes_manifest(workspace: dict) -> None:
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]
    mf_path = target / ".codex" / ".clasr-manifest" / f"{provider}.json"
    assert mf_path.exists()
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    assert mf["version"] == 1
    assert mf["provider"] == provider
    assert mf["platform"] == "codex"
    assert isinstance(mf["entries"], list)
    assert len(mf["entries"]) > 0


def test_install_manifest_entry_paths_are_relative(workspace: dict) -> None:
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]
    mf_path = target / ".codex" / ".clasr-manifest" / f"{provider}.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    for entry in mf["entries"]:
        path = entry["path"]
        assert not path.startswith("/"), f"Manifest path is absolute: {path}"


def test_install_manifest_symlink_target_is_absolute(workspace: dict) -> None:
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]
    mf_path = target / ".codex" / ".clasr-manifest" / f"{provider}.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    for entry in mf["entries"]:
        if entry["kind"] == "symlink":
            assert os.path.isabs(entry["target"]), \
                f"Symlink target not absolute: {entry['target']}"


# ---------------------------------------------------------------------------
# uninstall — full cleanup
# ---------------------------------------------------------------------------


def test_uninstall_removes_all(workspace: dict) -> None:
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    mf_path = target / ".codex" / ".clasr-manifest" / f"{provider}.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    uninstall(target, provider)

    assert not mf_path.exists()

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
    uninstall(target, provider="nonexistent")


def test_uninstall_scoped_rule_removes_nested_agents_md(tmp_path: Path) -> None:
    """Uninstalling removes nested AGENTS.md created by scoped rules."""
    src = _make_asr(tmp_path)
    (src / "rules" / "clasi-rules.md").write_text(
        "---\n"
        "codex:\n"
        "  applyTo: 'docs/clasi/**'\n"
        "---\n\n"
        "Always follow CLASI process.\n",
        encoding="utf-8",
    )

    target = tmp_path / "project"
    target.mkdir()
    install(source=src, target=target, provider="testprovider")

    nested = target / "docs" / "clasi" / "AGENTS.md"
    assert nested.exists()

    uninstall(target, provider="testprovider")

    assert not nested.exists(), "Scoped rule AGENTS.md should be removed on uninstall"


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
    """Verify clasr.platforms.codex has no 'from clasi' or 'import clasi' imports."""
    module_path = Path(__file__).parent.parent.parent / "clasr" / "platforms" / "codex.py"
    source = module_path.read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        assert not (stripped.startswith("from clasi") or stripped.startswith("import clasi")), \
            f"Found clasi import: {line!r}"
