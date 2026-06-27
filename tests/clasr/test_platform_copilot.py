"""
tests/clasr/test_platform_copilot.py

Tests for clasr.platforms.copilot — Copilot platform installer.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from clasr.platforms.copilot import CopilotIntegration

# Convenience aliases so test bodies read naturally without rewriting every call.
_integration = CopilotIntegration()
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
        "copilot: {}\n"
        "---\n\n"
        "Review the pull request carefully.\n",
        encoding="utf-8",
    )

    # rules/security.md (copilot has applyTo)
    rules_dir = src / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "security.md").write_text(
        "---\n"
        "description: Security rules\n"
        "copilot:\n"
        "  applyTo: '**'\n"
        "---\n\n"
        "Never expose secrets.\n",
        encoding="utf-8",
    )

    # copilot/ passthrough
    copilot_pass = src / "copilot"
    copilot_pass.mkdir(parents=True, exist_ok=True)
    (copilot_pass / "config.json").write_text(
        json.dumps({"model": "copilot-latest", "permissions": ["read"]}),
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


def test_install_creates_skills_symlink(workspace: dict) -> None:
    """Skills dir .github/skills is a symlink to .agents/skills."""
    install(**workspace)
    target = workspace["target"]
    github_skills = target / ".github" / "skills"
    agents_skills = target / ".agents" / "skills"

    assert github_skills.is_symlink(), ".github/skills should be a symlink"
    # The symlink should resolve to .agents/skills
    resolved = Path(os.readlink(github_skills))
    assert resolved == agents_skills.resolve() or resolved == agents_skills


def test_install_creates_agents_skills_entries(workspace: dict) -> None:
    """Per-skill SKILL.md entries are created under .agents/skills/."""
    install(**workspace)
    target = workspace["target"]
    alias = target / ".agents" / "skills" / "my-skill" / "SKILL.md"
    assert alias.exists()
    assert alias.is_symlink()
    assert os.path.isabs(os.readlink(alias))


def test_copy_mode(workspace: dict) -> None:
    """copy=True: .github/skills is a real directory, not a symlink."""
    workspace["copy"] = True
    install(**workspace)
    target = workspace["target"]
    github_skills = target / ".github" / "skills"

    assert github_skills.exists(), ".github/skills should exist"
    assert not github_skills.is_symlink(), ".github/skills should NOT be a symlink in copy mode"
    assert github_skills.is_dir(), ".github/skills should be a directory in copy mode"


def test_copy_mode_skill_files_not_symlinks(workspace: dict) -> None:
    """copy=True: per-skill SKILL.md entries are regular files, not symlinks."""
    workspace["copy"] = True
    install(**workspace)
    target = workspace["target"]
    alias = target / ".agents" / "skills" / "my-skill" / "SKILL.md"
    assert alias.exists()
    assert not alias.is_symlink(), "In copy mode, SKILL.md should be a copy not a symlink"


# ---------------------------------------------------------------------------
# install — agents
# ---------------------------------------------------------------------------


def test_install_renders_agents(workspace: dict) -> None:
    """Agents render to .github/agents/<n>.agent.md."""
    install(**workspace)
    target = workspace["target"]
    out = target / ".github" / "agents" / "code-review.agent.md"
    assert out.exists(), ".github/agents/code-review.agent.md should exist"
    text = out.read_text(encoding="utf-8")
    assert "code-review" in text


def test_install_agents_no_claude_specific(workspace: dict) -> None:
    """Rendered agent file should not contain claude-specific fields."""
    install(**workspace)
    target = workspace["target"]
    out = target / ".github" / "agents" / "code-review.agent.md"
    text = out.read_text(encoding="utf-8")
    # claude: block should be stripped from projected output
    assert "claude:" not in text


# ---------------------------------------------------------------------------
# install — rules
# ---------------------------------------------------------------------------


def test_install_renders_rules(workspace: dict) -> None:
    """Rules render to .github/instructions/<n>.instructions.md."""
    install(**workspace)
    target = workspace["target"]
    out = target / ".github" / "instructions" / "security.instructions.md"
    assert out.exists(), ".github/instructions/security.instructions.md should exist"
    text = out.read_text(encoding="utf-8")
    assert "Never expose secrets" in text


def test_install_rules_preserve_apply_to(workspace: dict) -> None:
    """Rendered rule file preserves applyTo: from projected frontmatter."""
    install(**workspace)
    target = workspace["target"]
    out = target / ".github" / "instructions" / "security.instructions.md"
    text = out.read_text(encoding="utf-8")
    assert "applyTo" in text, "applyTo: field should be in rendered instructions file"


# ---------------------------------------------------------------------------
# install — marker block (copilot-instructions.md ONLY)
# ---------------------------------------------------------------------------


def test_install_writes_copilot_instructions_block(workspace: dict) -> None:
    """.github/copilot-instructions.md contains named marker block."""
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]
    copilot_instr = target / ".github" / "copilot-instructions.md"
    assert copilot_instr.exists(), ".github/copilot-instructions.md should exist"
    text = copilot_instr.read_text(encoding="utf-8")
    assert f"<!-- BEGIN clasr:{provider} -->" in text


def test_install_marker_block_content(workspace: dict) -> None:
    """source/AGENTS.md content is inside the copilot-instructions.md block."""
    install(**workspace)
    target = workspace["target"]
    text = (target / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    assert "Use clasr" in text or "multi-platform" in text.lower()


def test_install_no_root_agents_md(workspace: dict) -> None:
    """Copilot installer must NOT write root AGENTS.md."""
    install(**workspace)
    agents_md = workspace["target"] / "AGENTS.md"
    assert not agents_md.exists(), "Copilot should not create root AGENTS.md"


def test_install_no_claude_md(workspace: dict) -> None:
    """Copilot installer must NOT write CLAUDE.md."""
    install(**workspace)
    claude_md = workspace["target"] / "CLAUDE.md"
    assert not claude_md.exists(), "Copilot should not create CLAUDE.md"


# ---------------------------------------------------------------------------
# install — passthrough (JSON)
# ---------------------------------------------------------------------------


def test_install_passthrough_json(workspace: dict) -> None:
    """Passthrough JSON file is written to .github/."""
    install(**workspace)
    config = workspace["target"] / ".github" / "config.json"
    assert config.exists()
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["model"] == "copilot-latest"


def test_install_json_merged(tmp_path: Path) -> None:
    """When dest JSON already exists (another provider), merge keys."""
    source = _make_asr(tmp_path)

    # Add a .vscode/mcp.json passthrough for JSON-merge testing
    vscode_dir = source / "copilot" / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)
    (vscode_dir / "mcp.json").write_text(
        json.dumps({"servers": {"myserver": {"url": "http://localhost"}}}),
        encoding="utf-8",
    )

    target = tmp_path / "project"
    target.mkdir()
    github_dir = target / ".github"
    github_dir.mkdir()

    # Pre-create .vscode/mcp.json as if another provider owns it
    existing_vscode = github_dir / ".vscode"
    existing_vscode.mkdir()
    existing_mcp = {"servers": {"otherserver": {"url": "http://other"}}}
    (existing_vscode / "mcp.json").write_text(
        json.dumps(existing_mcp), encoding="utf-8"
    )

    # Write a fake manifest for the other provider
    other_manifest = {
        "version": 1,
        "provider": "otherprovider",
        "platform": "copilot",
        "source": "/fake",
        "entries": [
            {"path": ".github/.vscode/mcp.json", "kind": "copy"},
        ],
    }
    manifest_dir = github_dir / ".clasr-manifest"
    manifest_dir.mkdir()
    (manifest_dir / "otherprovider.json").write_text(
        json.dumps(other_manifest), encoding="utf-8"
    )

    install(source, target, provider="testprovider")

    mcp = github_dir / ".vscode" / "mcp.json"
    assert mcp.exists()
    data = json.loads(mcp.read_text(encoding="utf-8"))
    # Both providers' server keys should be present
    assert "myserver" in data.get("servers", {})
    assert "otherserver" in data.get("servers", {})

    # Manifest should record json-merged
    mf_path = manifest_dir / "testprovider.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))
    json_merged_entries = [e for e in mf["entries"] if e["kind"] == "json-merged"]
    assert len(json_merged_entries) == 1


# ---------------------------------------------------------------------------
# install — non-JSON collision
# ---------------------------------------------------------------------------


def test_install_nonjson_collision_raises(tmp_path: Path) -> None:
    """Non-JSON passthrough: collision with another provider raises."""
    source = _make_asr(tmp_path)

    # Add a non-JSON passthrough file
    (source / "copilot" / "custom.md").write_text("# Custom", encoding="utf-8")

    target = tmp_path / "project"
    target.mkdir()
    github_dir = target / ".github"
    github_dir.mkdir()

    # Pre-create the file as if another provider owns it
    (github_dir / "custom.md").write_text("# Owned by other", encoding="utf-8")

    manifest_dir = github_dir / ".clasr-manifest"
    manifest_dir.mkdir()
    (manifest_dir / "rivalprovider.json").write_text(
        json.dumps({
            "version": 1,
            "provider": "rivalprovider",
            "platform": "copilot",
            "source": "/fake",
            "entries": [{"path": ".github/custom.md", "kind": "copy"}],
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
    """Manifest is written to .github/.clasr-manifest/<provider>.json."""
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]
    mf_path = target / ".github" / ".clasr-manifest" / f"{provider}.json"
    assert mf_path.exists()
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    assert mf["version"] == 1
    assert mf["provider"] == provider
    assert mf["platform"] == "copilot"
    assert isinstance(mf["entries"], list)
    assert len(mf["entries"]) > 0


def test_install_manifest_has_skills_directory_entry(workspace: dict) -> None:
    """Manifest has an entry for .github/skills directory alias."""
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]
    mf_path = target / ".github" / ".clasr-manifest" / f"{provider}.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    dir_entries = [e for e in mf["entries"] if e.get("path") == ".github/skills"]
    assert len(dir_entries) == 1, "Manifest should have exactly one .github/skills entry"
    assert dir_entries[0]["kind"] in ("symlink", "copy")


def test_install_manifest_has_per_skill_entries(workspace: dict) -> None:
    """Manifest has entries for each SKILL.md under .agents/skills/."""
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]
    mf_path = target / ".github" / ".clasr-manifest" / f"{provider}.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    skill_entries = [e for e in mf["entries"] if ".agents/skills/" in e.get("path", "")]
    assert len(skill_entries) >= 1, "Manifest should have per-skill .agents/skills/ entries"


def test_install_manifest_entry_paths_are_relative(workspace: dict) -> None:
    """All manifest entry paths are relative (not absolute)."""
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]
    mf_path = target / ".github" / ".clasr-manifest" / f"{provider}.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    for entry in mf["entries"]:
        path = entry["path"]
        assert not path.startswith("/"), f"Manifest path is absolute: {path}"


# ---------------------------------------------------------------------------
# uninstall — full cleanup
# ---------------------------------------------------------------------------


def test_uninstall_removes_all(workspace: dict) -> None:
    """After install+uninstall, all installed files and manifest are gone."""
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    mf_path = target / ".github" / ".clasr-manifest" / f"{provider}.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    uninstall(target, provider)

    assert not mf_path.exists(), "Manifest file should be deleted after uninstall"

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


def test_uninstall_strips_copilot_instructions_block(workspace: dict) -> None:
    """Uninstall strips the marker block from .github/copilot-instructions.md."""
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    copilot_instr = target / ".github" / "copilot-instructions.md"
    assert copilot_instr.exists()
    text_before = copilot_instr.read_text(encoding="utf-8")
    assert f"<!-- BEGIN clasr:{provider} -->" in text_before

    uninstall(target, provider)

    if copilot_instr.exists():
        text_after = copilot_instr.read_text(encoding="utf-8")
        assert f"<!-- BEGIN clasr:{provider} -->" not in text_after


def test_uninstall_idempotent_no_manifest(tmp_path: Path) -> None:
    """Uninstall with no manifest should not raise."""
    target = tmp_path / "project"
    target.mkdir()
    uninstall(target, provider="nonexistent")


def test_uninstall_copy_mode_removes_directory(workspace: dict) -> None:
    """Uninstall in copy mode removes .github/skills directory tree."""
    workspace["copy"] = True
    install(**workspace)
    target = workspace["target"]
    provider = workspace["provider"]

    github_skills = target / ".github" / "skills"
    assert github_skills.is_dir() and not github_skills.is_symlink()

    uninstall(target, provider)

    assert not github_skills.exists(), ".github/skills dir should be removed after uninstall"


def test_uninstall_json_merged_removes_keys(tmp_path: Path) -> None:
    """After merging two providers, uninstalling one leaves the other's keys."""
    source = _make_asr(tmp_path)
    target = tmp_path / "project"
    target.mkdir()
    github_dir = target / ".github"
    github_dir.mkdir()

    # Pre-install "otherprovider" with its own config
    other_config = {"debug": True, "theme": "dark"}
    (github_dir / "config.json").write_text(
        json.dumps(other_config), encoding="utf-8"
    )
    manifest_dir = github_dir / ".clasr-manifest"
    manifest_dir.mkdir()
    (manifest_dir / "otherprovider.json").write_text(
        json.dumps({
            "version": 1,
            "provider": "otherprovider",
            "platform": "copilot",
            "source": "/fake",
            "entries": [{"path": ".github/config.json", "kind": "copy"}],
        }),
        encoding="utf-8",
    )

    install(source, target, provider="testprovider")

    data = json.loads((github_dir / "config.json").read_text(encoding="utf-8"))
    assert "model" in data
    assert "debug" in data

    uninstall(target, provider="testprovider")

    data_after = json.loads((github_dir / "config.json").read_text(encoding="utf-8"))
    assert "model" not in data_after   # testprovider contributed this
    assert "debug" in data_after       # otherprovider owns this — untouched

    assert not (manifest_dir / "testprovider.json").exists()


def test_uninstall_json_merged_empty_deletes_file(tmp_path: Path) -> None:
    """When uninstalling removes all keys, delete the file."""
    source = _make_asr(tmp_path)
    target = tmp_path / "project"
    target.mkdir()

    install(source, target, provider="testprovider")

    config = target / ".github" / "config.json"
    assert config.exists()

    # Replace the manifest entry with json-merged so uninstall pops all keys
    mf_path = target / ".github" / ".clasr-manifest" / "testprovider.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8"))
    for e in mf["entries"]:
        if e["path"] == ".github/config.json":
            e["kind"] = "json-merged"
            e["keys"] = list(json.loads(config.read_text(encoding="utf-8")).keys())
    mf_path.write_text(json.dumps(mf), encoding="utf-8")

    uninstall(target, provider="testprovider")

    assert not config.exists()


# ---------------------------------------------------------------------------
# source directory immutability
# ---------------------------------------------------------------------------


def test_source_dir_immutable(workspace: dict) -> None:
    """install() must not modify the source directory."""
    source = workspace["source"]
    hash_before = _dir_hash(source)
    install(**workspace)
    hash_after = _dir_hash(source)
    assert hash_before == hash_after, "install() modified the source directory"


# ---------------------------------------------------------------------------
# no clasi imports
# ---------------------------------------------------------------------------


def test_no_clasi_imports() -> None:
    """Verify clasr.platforms.copilot has no 'from clasi' or 'import clasi' imports."""
    module_path = Path(__file__).parent.parent.parent / "src" / "clasr" / "platforms" / "copilot.py"
    source = module_path.read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        assert not (stripped.startswith("from clasi") or stripped.startswith("import clasi")), \
            f"Found clasi import: {line!r}"
