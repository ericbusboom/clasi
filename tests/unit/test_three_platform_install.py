"""
tests/unit/test_three_platform_install.py

End-to-end three-platform install test and CI drift verifier.

Ticket: 013-012
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List

import pytest
import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from clasi.init_command import run_init
from clasi.platforms.claude import _PLUGIN_DIR as CLAUDE_PLUGIN_DIR


# ---------------------------------------------------------------------------
# Helper: drift verifier
# ---------------------------------------------------------------------------


def check_drift(target: Path) -> List[str]:
    """Verify all (canonical, alias) pairs in a CLASI install.

    For each known canonical/alias pair:
    - If the alias is a symlink: assert it resolves to the canonical.
    - If the alias is a regular file: assert its content matches the canonical.

    Returns a list of mismatch messages (empty list = no drift).
    """
    mismatches: List[str] = []

    # ---- AGENTS.md and CLAUDE.md ----------------------------------------
    # Both files are independent regular files that each carry the CLASI
    # marker block. They are NOT required to be byte-identical (CLAUDE.md
    # may contain other tools' marker blocks too). Drift is reported only
    # if a file exists but is missing its CLASI block.
    for label, path in (("AGENTS.md", target / "AGENTS.md"),
                        ("CLAUDE.md", target / "CLAUDE.md")):
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if "<!-- CLASI:START -->" not in content:
                mismatches.append(
                    f"{label} exists but is missing the CLASI marker block"
                )

    # ---- .agents/skills/<n>/SKILL.md <-> .claude/skills/<n>/SKILL.md -----
    agents_skills_dir = target / ".agents" / "skills"
    claude_skills_dir = target / ".claude" / "skills"
    if agents_skills_dir.is_dir():
        for skill_dir in sorted(agents_skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            canonical = skill_dir / "SKILL.md"
            if not canonical.exists():
                continue
            alias = claude_skills_dir / skill_dir.name / "SKILL.md"
            if not alias.exists() and not alias.is_symlink():
                continue  # Claude may not be installed — skip
            if alias.is_symlink():
                resolved = alias.resolve()
                expected = canonical.resolve()
                if resolved != expected:
                    mismatches.append(
                        f".claude/skills/{skill_dir.name}/SKILL.md symlink resolves to "
                        f"{resolved}, expected {expected}"
                    )
            else:
                if alias.read_bytes() != canonical.read_bytes():
                    mismatches.append(
                        f".claude/skills/{skill_dir.name}/SKILL.md content does not "
                        f"match canonical (drift detected)"
                    )

    # ---- .agents/skills/<n>/SKILL.md <-> .github/skills/<n>/SKILL.md -----
    # Copilot uses a directory-level symlink: .github/skills -> .agents/skills.
    # We verify the directory symlink itself, then check per-skill files resolve
    # through it correctly.
    github_skills = target / ".github" / "skills"
    if github_skills.exists() or github_skills.is_symlink():
        if github_skills.is_symlink():
            resolved_dir = github_skills.resolve()
            expected_dir = agents_skills_dir.resolve()
            if resolved_dir != expected_dir:
                mismatches.append(
                    f".github/skills/ symlink resolves to {resolved_dir}, "
                    f"expected {expected_dir}"
                )
        elif agents_skills_dir.is_dir():
            # Copy mode: directory exists as a real dir — check per-file content
            for skill_dir in sorted(agents_skills_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue
                canonical = skill_dir / "SKILL.md"
                if not canonical.exists():
                    continue
                alias = github_skills / skill_dir.name / "SKILL.md"
                if not alias.exists():
                    continue
                if alias.read_bytes() != canonical.read_bytes():
                    mismatches.append(
                        f".github/skills/{skill_dir.name}/SKILL.md content does not "
                        f"match canonical (drift detected)"
                    )

    return mismatches


# ---------------------------------------------------------------------------
# End-to-end three-platform install test
# ---------------------------------------------------------------------------


def test_three_platform_install_end_to_end(tmp_path: Path) -> None:
    """Install with --claude --codex --copilot and validate all emitted files.

    This is the canonical regression guard for the three-platform install.
    """
    run_init(str(tmp_path), claude=True, codex=True, copilot=True)

    plugin_skills = CLAUDE_PLUGIN_DIR / "skills"
    expected_skills = sorted(
        d.name
        for d in plugin_skills.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    )
    assert len(expected_skills) == 25, (
        f"Expected 25 bundled skills, found {len(expected_skills)}"
    )

    # ------------------------------------------------------------------
    # Canonical .agents/skills/<n>/SKILL.md — all 25 exist
    # ------------------------------------------------------------------
    for skill_name in expected_skills:
        canonical = tmp_path / ".agents" / "skills" / skill_name / "SKILL.md"
        assert canonical.exists(), (
            f".agents/skills/{skill_name}/SKILL.md must exist (canonical)"
        )

    # ------------------------------------------------------------------
    # .claude/skills/<n>/SKILL.md — symlinks to canonical
    # ------------------------------------------------------------------
    for skill_name in expected_skills:
        alias = tmp_path / ".claude" / "skills" / skill_name / "SKILL.md"
        assert alias.is_symlink(), (
            f".claude/skills/{skill_name}/SKILL.md must be a symlink"
        )
        assert alias.resolve() == (tmp_path / ".agents" / "skills" / skill_name / "SKILL.md").resolve(), (
            f".claude/skills/{skill_name}/SKILL.md must resolve to canonical"
        )

    # ------------------------------------------------------------------
    # .github/skills/ — directory-level symlink to .agents/skills/
    # ------------------------------------------------------------------
    github_skills = tmp_path / ".github" / "skills"
    assert github_skills.is_symlink(), ".github/skills/ must be a symlink"
    assert github_skills.resolve() == (tmp_path / ".agents" / "skills").resolve(), (
        ".github/skills/ must resolve to .agents/skills/"
    )

    # ------------------------------------------------------------------
    # No SKILL.md content duplication: alias paths must all be symlinks,
    # not regular file copies (in default mode)
    # ------------------------------------------------------------------
    for skill_name in expected_skills:
        claude_alias = tmp_path / ".claude" / "skills" / skill_name / "SKILL.md"
        assert not claude_alias.is_file() or claude_alias.is_symlink(), (
            f".claude/skills/{skill_name}/SKILL.md must not be a regular file copy"
        )

    # ------------------------------------------------------------------
    # CLAUDE.md — regular file with the CLASI marker block (no longer
    # a symlink; both files hold their own copy of the block so CLASI
    # coexists cleanly with other tools' marker blocks in CLAUDE.md).
    # ------------------------------------------------------------------
    claude_md = tmp_path / "CLAUDE.md"
    agents_md = tmp_path / "AGENTS.md"
    assert claude_md.exists() and not claude_md.is_symlink(), (
        "CLAUDE.md must be a regular file"
    )
    claude_content = claude_md.read_text(encoding="utf-8")
    assert "<!-- CLASI:START -->" in claude_content
    assert "<!-- CLASI:END -->" in claude_content

    # ------------------------------------------------------------------
    # AGENTS.md — exists, parses, contains CLASI marker block
    # ------------------------------------------------------------------
    assert agents_md.exists(), "AGENTS.md must exist"
    agents_content = agents_md.read_text(encoding="utf-8")
    assert "<!-- CLASI:START -->" in agents_content, (
        "AGENTS.md must contain <!-- CLASI:START -->"
    )
    assert "<!-- CLASI:END -->" in agents_content, (
        "AGENTS.md must contain <!-- CLASI:END -->"
    )

    # ------------------------------------------------------------------
    # .claude/rules/*.md — 5 rule files
    # ------------------------------------------------------------------
    rules_dir = tmp_path / ".claude" / "rules"
    assert rules_dir.is_dir(), ".claude/rules/ must exist"
    rule_files = list(rules_dir.glob("*.md"))
    assert len(rule_files) >= 5, (
        f".claude/rules/ must contain at least 5 .md files, found {len(rule_files)}"
    )

    # ------------------------------------------------------------------
    # .codex/agents/*.toml — 3 agents, each parseable
    # ------------------------------------------------------------------
    codex_agents_dir = tmp_path / ".codex" / "agents"
    assert codex_agents_dir.is_dir(), ".codex/agents/ must exist"
    codex_agent_files = list(codex_agents_dir.glob("*.toml"))
    assert len(codex_agent_files) >= 3, (
        f".codex/agents/ must contain at least 3 .toml files, found {len(codex_agent_files)}"
    )
    for toml_file in codex_agent_files:
        data = tomllib.loads(toml_file.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{toml_file.name} must parse to a dict"
        assert "name" in data, f"{toml_file.name} must have 'name' field"

    # ------------------------------------------------------------------
    # .github/copilot-instructions.md — exists with marker block
    # ------------------------------------------------------------------
    copilot_instr = tmp_path / ".github" / "copilot-instructions.md"
    assert copilot_instr.exists(), ".github/copilot-instructions.md must exist"
    copilot_content = copilot_instr.read_text(encoding="utf-8")
    assert "<!-- CLASI:START -->" in copilot_content, (
        ".github/copilot-instructions.md must contain CLASI marker block"
    )

    # ------------------------------------------------------------------
    # .github/instructions/*.instructions.md — files with applyTo: frontmatter
    # ------------------------------------------------------------------
    instr_dir = tmp_path / ".github" / "instructions"
    assert instr_dir.is_dir(), ".github/instructions/ must exist"
    instr_files = list(instr_dir.glob("*.instructions.md"))
    assert len(instr_files) >= 3, (
        f".github/instructions/ must contain at least 3 files, found {len(instr_files)}"
    )
    for instr_file in instr_files:
        content = instr_file.read_text(encoding="utf-8")
        parts = content.split("---", maxsplit=2)
        assert len(parts) >= 3, (
            f"{instr_file.name} must have YAML frontmatter delimiters"
        )
        fm = yaml.safe_load(parts[1])
        assert fm is not None, f"{instr_file.name} frontmatter must not be empty"
        assert "applyTo" in fm, f"{instr_file.name} frontmatter must contain 'applyTo'"

    # ------------------------------------------------------------------
    # .github/agents/*.agent.md — 3 agent files with valid YAML frontmatter
    # ------------------------------------------------------------------
    github_agents_dir = tmp_path / ".github" / "agents"
    assert github_agents_dir.is_dir(), ".github/agents/ must exist"
    agent_files = list(github_agents_dir.glob("*.agent.md"))
    assert len(agent_files) >= 3, (
        f".github/agents/ must contain at least 3 .agent.md files, found {len(agent_files)}"
    )
    for agent_file in agent_files:
        content = agent_file.read_text(encoding="utf-8")
        parts = content.split("---", maxsplit=2)
        assert len(parts) >= 3, (
            f"{agent_file.name} must have YAML frontmatter delimiters"
        )
        fm = yaml.safe_load(parts[1])
        assert fm is not None, f"{agent_file.name} frontmatter must not be empty"
        assert "description" in fm, (
            f"{agent_file.name} frontmatter must contain 'description'"
        )

    # ------------------------------------------------------------------
    # .vscode/mcp.json — valid JSON with servers.clasi present
    # ------------------------------------------------------------------
    vscode_mcp = tmp_path / ".vscode" / "mcp.json"
    assert vscode_mcp.exists(), ".vscode/mcp.json must exist"
    vscode_data = json.loads(vscode_mcp.read_text(encoding="utf-8"))
    assert "servers" in vscode_data, ".vscode/mcp.json must have 'servers' key"
    assert "clasi" in vscode_data["servers"], (
        ".vscode/mcp.json must have servers.clasi"
    )

    # ------------------------------------------------------------------
    # .codex/config.toml — valid TOML with mcp_servers.clasi
    # ------------------------------------------------------------------
    codex_config = tmp_path / ".codex" / "config.toml"
    assert codex_config.exists(), ".codex/config.toml must exist"
    codex_data = tomllib.loads(codex_config.read_text(encoding="utf-8"))
    assert "mcp_servers" in codex_data, ".codex/config.toml must have [mcp_servers]"
    assert "clasi" in codex_data["mcp_servers"], (
        ".codex/config.toml must have [mcp_servers.clasi]"
    )

    # ------------------------------------------------------------------
    # .codex/hooks.json — valid JSON with correct schema
    # ------------------------------------------------------------------
    codex_hooks = tmp_path / ".codex" / "hooks.json"
    assert codex_hooks.exists(), ".codex/hooks.json must exist"
    hooks_data = json.loads(codex_hooks.read_text(encoding="utf-8"))
    assert "hooks" in hooks_data, ".codex/hooks.json must have 'hooks' key"
    assert "Stop" in hooks_data["hooks"], ".codex/hooks.json must have hooks.Stop"

    # ------------------------------------------------------------------
    # docs/clasi/AGENTS.md, docs/clasi/todo/AGENTS.md, clasi/AGENTS.md
    # ------------------------------------------------------------------
    docs_clasi_agents = tmp_path / "docs" / "clasi" / "AGENTS.md"
    assert docs_clasi_agents.exists(), "docs/clasi/AGENTS.md must exist"
    assert docs_clasi_agents.read_text(encoding="utf-8").strip(), (
        "docs/clasi/AGENTS.md must have content"
    )

    docs_clasi_todo_agents = tmp_path / "docs" / "clasi" / "todo" / "AGENTS.md"
    assert docs_clasi_todo_agents.exists(), "docs/clasi/todo/AGENTS.md must exist"
    assert docs_clasi_todo_agents.read_text(encoding="utf-8").strip(), (
        "docs/clasi/todo/AGENTS.md must have content"
    )

    clasi_agents = tmp_path / "clasi" / "AGENTS.md"
    assert clasi_agents.exists(), "clasi/AGENTS.md must exist"
    assert clasi_agents.read_text(encoding="utf-8").strip(), (
        "clasi/AGENTS.md must have content"
    )


# ---------------------------------------------------------------------------
# CI drift verifier tests
# ---------------------------------------------------------------------------


def test_drift_verifier_clean_install(tmp_path: Path) -> None:
    """check_drift() must return an empty list for a clean three-platform install."""
    run_init(str(tmp_path), claude=True, codex=True, copilot=True)
    mismatches = check_drift(tmp_path)
    assert mismatches == [], (
        f"Expected no drift in a clean install, found:\n" + "\n".join(mismatches)
    )


def test_drift_verifier_detects_missing_claude_md_block(tmp_path: Path) -> None:
    """check_drift() must report when CLAUDE.md exists but lacks the CLASI block.

    Under the new model, CLAUDE.md and AGENTS.md are independent regular
    files; they don't need to be byte-identical (CLAUDE.md may carry other
    tools' marker blocks too). The only drift condition is a CLAUDE.md
    that exists without the CLASI block.
    """
    run_init(str(tmp_path), claude=True, codex=True, copilot=True)

    # Wipe the CLASI block out of CLAUDE.md (simulating someone removing
    # the block by hand without uninstalling).
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(
        "# Just user content, no CLASI block.\n", encoding="utf-8"
    )

    mismatches = check_drift(tmp_path)
    assert any("CLAUDE.md" in m for m in mismatches), (
        f"Mismatch message must mention CLAUDE.md, got: {mismatches}"
    )


def test_drift_verifier_detects_skill_mismatch(tmp_path: Path) -> None:
    """check_drift() must detect when a skill alias content diverges from canonical."""
    run_init(str(tmp_path), claude=True, codex=True, copilot=True)

    # Find the first skill alias and convert it to a diverged regular file
    agents_skills = tmp_path / ".agents" / "skills"
    skill_name = sorted(d.name for d in agents_skills.iterdir() if d.is_dir())[0]
    canonical = agents_skills / skill_name / "SKILL.md"
    alias = tmp_path / ".claude" / "skills" / skill_name / "SKILL.md"

    original_content = canonical.read_bytes()
    alias.unlink()  # remove symlink
    alias.write_bytes(original_content + b"\n\n# Diverged content\n")

    mismatches = check_drift(tmp_path)
    assert len(mismatches) >= 1, (
        "check_drift() must report at least one mismatch when a skill alias diverges"
    )
    assert any(skill_name in m for m in mismatches), (
        f"Mismatch message must mention the skill name '{skill_name}', got: {mismatches}"
    )


def test_drift_verifier_reports_all_mismatches(tmp_path: Path) -> None:
    """check_drift() must report all mismatches, not just the first."""
    run_init(str(tmp_path), claude=True, codex=True, copilot=True)

    agents_skills = tmp_path / ".agents" / "skills"
    skill_names = sorted(d.name for d in agents_skills.iterdir() if d.is_dir())[:2]

    # Break two skill aliases
    for skill_name in skill_names:
        canonical = agents_skills / skill_name / "SKILL.md"
        original_content = canonical.read_bytes()
        alias = tmp_path / ".claude" / "skills" / skill_name / "SKILL.md"
        alias.unlink()
        alias.write_bytes(original_content + b"\n# Drift\n")

    mismatches = check_drift(tmp_path)
    assert len(mismatches) >= 2, (
        f"Expected at least 2 mismatches reported, got {len(mismatches)}: {mismatches}"
    )
