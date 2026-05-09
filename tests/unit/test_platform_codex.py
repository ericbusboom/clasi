"""Tests for clasi/platforms/codex.py — Codex installer and uninstaller."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from clasi.platforms.codex import (
    _ACTIVE_AGENTS,
    _CLASI_HOOK_COMMAND,
    _CLASI_SRC_RULES,
    _CLASI_STOP_HOOK_OLD,
    _CLASI_STOP_HOOK_WRAPPER,
    _build_clasi_dir_content,
    _build_issues_dir_content,
    install,
    uninstall,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_MCP_CONFIG = {
    "command": "clasi",
    "args": ["mcp"],
    "env": {},
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Return a fresh empty project directory."""
    d = tmp_path / "project"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# test_codex_install_creates_all_artifacts
# ---------------------------------------------------------------------------


def test_codex_install_creates_all_artifacts(project: Path) -> None:
    """install() creates all four Codex artifacts from scratch."""
    install(project, _MCP_CONFIG)

    # 1. AGENTS.md
    agents_md = project / "AGENTS.md"
    assert agents_md.exists(), "AGENTS.md should be created"
    content = agents_md.read_text(encoding="utf-8")
    assert "<!-- CLASI:START -->" in content
    assert "<!-- CLASI:END -->" in content
    assert ".codex/agents/team-lead.toml" in content, (
        "AGENTS.md must point the agent at the team-lead role definition"
    )
    assert "you ARE the team-lead" in content, (
        "AGENTS.md must make the team-lead identity explicit"
    )
    assert "Available skills: run" not in content, "CLASI section must not contain the /se dispatcher line"
    assert "run `/se` for a list" not in content, "CLASI section must not contain the /se dispatcher line"

    # 2. .codex/config.toml
    config_path = project / ".codex" / "config.toml"
    assert config_path.exists(), ".codex/config.toml should be created"
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert "mcp_servers" in data
    assert "clasi" in data["mcp_servers"]
    assert data["mcp_servers"]["clasi"]["command"] == "clasi"
    assert data["codex_hooks"] is True

    # 3. .codex/hooks.json — new wrapper format
    hooks_path = project / ".codex" / "hooks.json"
    assert hooks_path.exists(), ".codex/hooks.json should be created"
    hooks_data = json.loads(hooks_path.read_text(encoding="utf-8"))
    stop_list = hooks_data["hooks"]["Stop"]
    # Wrapper entry must be present; old flat entry must be absent.
    assert _CLASI_STOP_HOOK_WRAPPER in stop_list
    assert _CLASI_STOP_HOOK_OLD not in stop_list
    # "args" key must not appear in any handler within our wrapper.
    for handler in _CLASI_STOP_HOOK_WRAPPER["hooks"]:
        assert "args" not in handler

    # 4. .agents/skills/se/SKILL.md
    skill = project / ".agents" / "skills" / "se" / "SKILL.md"
    assert skill.exists(), ".agents/skills/se/SKILL.md should be created"
    skill_content = skill.read_text(encoding="utf-8")
    assert "description:" in skill_content


# ---------------------------------------------------------------------------
# test_codex_install_idempotent
# ---------------------------------------------------------------------------


def test_codex_install_idempotent(project: Path) -> None:
    """Running install() twice produces no duplication in any file."""
    install(project, _MCP_CONFIG)
    install(project, _MCP_CONFIG)

    # AGENTS.md: marker block appears exactly once
    agents_md = project / "AGENTS.md"
    content = agents_md.read_text(encoding="utf-8")
    assert content.count("<!-- CLASI:START -->") == 1
    assert content.count("<!-- CLASI:END -->") == 1

    # .codex/config.toml: mcp_servers.clasi appears once
    config_path = project / ".codex" / "config.toml"
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert len([k for k in data.get("mcp_servers", {}) if k == "clasi"]) == 1
    assert data["codex_hooks"] is True

    # .codex/hooks.json: Stop list contains exactly one CLASI wrapper entry
    hooks_path = project / ".codex" / "hooks.json"
    hooks_data = json.loads(hooks_path.read_text(encoding="utf-8"))
    stop_list = hooks_data["hooks"]["Stop"]
    clasi_entries = [e for e in stop_list if e == _CLASI_STOP_HOOK_WRAPPER]
    assert len(clasi_entries) == 1
    # Old flat format must not appear at all.
    assert _CLASI_STOP_HOOK_OLD not in stop_list

    # .agents/skills/se/SKILL.md: still exists and is a regular file
    skill = project / ".agents" / "skills" / "se" / "SKILL.md"
    assert skill.exists()


# ---------------------------------------------------------------------------
# test_codex_install_agents_md_preserves_user_content
# ---------------------------------------------------------------------------


def test_codex_install_agents_md_preserves_user_content(project: Path) -> None:
    """install() preserves user content in AGENTS.md outside the CLASI block."""
    user_content = "# My custom agent instructions\n\nDo things my way.\n"
    agents_md = project / "AGENTS.md"
    agents_md.write_text(user_content, encoding="utf-8")

    install(project, _MCP_CONFIG)

    content = agents_md.read_text(encoding="utf-8")
    assert "My custom agent instructions" in content
    assert "Do things my way" in content
    assert "<!-- CLASI:START -->" in content
    assert "<!-- CLASI:END -->" in content


# ---------------------------------------------------------------------------
# test_codex_uninstall_removes_clasi_sections
# ---------------------------------------------------------------------------


def test_codex_uninstall_removes_clasi_sections(project: Path) -> None:
    """install then uninstall leaves no CLASI artifacts."""
    install(project, _MCP_CONFIG)
    uninstall(project)

    # AGENTS.md deleted (was only CLASI content)
    agents_md = project / "AGENTS.md"
    assert not agents_md.exists(), "AGENTS.md should be deleted when only CLASI content"

    # .codex/config.toml deleted (was only CLASI content)
    config_path = project / ".codex" / "config.toml"
    assert not config_path.exists(), ".codex/config.toml should be deleted"

    # .codex/hooks.json deleted (was only CLASI content)
    hooks_path = project / ".codex" / "hooks.json"
    assert not hooks_path.exists(), ".codex/hooks.json should be deleted"

    # .agents/skills/se/SKILL.md deleted
    skill = project / ".agents" / "skills" / "se" / "SKILL.md"
    assert not skill.exists()


def test_codex_uninstall_preserves_user_content(project: Path) -> None:
    """uninstall() preserves user content in AGENTS.md outside the CLASI block."""
    user_content = "# My custom agent instructions\n\nDo things my way.\n"
    agents_md = project / "AGENTS.md"
    agents_md.write_text(user_content, encoding="utf-8")

    install(project, _MCP_CONFIG)
    uninstall(project)

    assert agents_md.exists(), "AGENTS.md should survive when user content is present"
    content = agents_md.read_text(encoding="utf-8")
    assert "My custom agent instructions" in content
    assert "Do things my way" in content
    assert "<!-- CLASI:START -->" not in content
    assert "<!-- CLASI:END -->" not in content


def test_codex_uninstall_preserves_other_mcp_servers(project: Path) -> None:
    """uninstall() leaves other [mcp_servers] entries in .codex/config.toml intact."""
    install(project, _MCP_CONFIG)

    # Add a third-party mcp_server entry manually
    config_path = project / ".codex" / "config.toml"
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    data["mcp_servers"]["other-tool"] = {"command": "other", "args": []}
    import tomli_w
    config_path.write_text(tomli_w.dumps(data), encoding="utf-8")

    uninstall(project)

    assert config_path.exists(), "config.toml should survive when other entries present"
    remaining = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert "clasi" not in remaining.get("mcp_servers", {})
    assert "codex_hooks" not in remaining
    assert "other-tool" in remaining.get("mcp_servers", {})


def test_codex_uninstall_preserves_other_stop_hooks(project: Path) -> None:
    """uninstall() leaves non-CLASI Stop hook entries in .codex/hooks.json intact."""
    install(project, _MCP_CONFIG)

    # Add a user-defined Stop hook entry (in wrapper format, like a real user entry).
    hooks_path = project / ".codex" / "hooks.json"
    data = json.loads(hooks_path.read_text(encoding="utf-8"))
    data["hooks"]["Stop"].append(
        {"hooks": [{"type": "command", "command": "my-tool --check", "timeout": 10}]}
    )
    hooks_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    uninstall(project)

    assert hooks_path.exists(), "hooks.json should survive when other hooks present"
    remaining = json.loads(hooks_path.read_text(encoding="utf-8"))
    stop_list = remaining.get("hooks", {}).get("Stop", [])
    # CLASI wrapper entry must be gone.
    clasi_entries = [e for e in stop_list if e == _CLASI_STOP_HOOK_WRAPPER]
    assert len(clasi_entries) == 0
    # User entry must remain.
    user_entries = [
        e for e in stop_list
        if isinstance(e, dict)
        and any(h.get("command") == "my-tool --check" for h in e.get("hooks", []))
    ]
    assert len(user_entries) == 1


# ---------------------------------------------------------------------------
# test_codex_uninstall_partial (idempotency when files are missing)
# ---------------------------------------------------------------------------


def test_codex_uninstall_partial_no_files(project: Path) -> None:
    """uninstall() on a clean directory raises no errors."""
    # Should complete without exception
    uninstall(project)


def test_codex_uninstall_partial_only_agents_md(project: Path) -> None:
    """uninstall() when only AGENTS.md exists raises no errors."""
    agents_md = project / "AGENTS.md"
    agents_md.write_text(
        "<!-- CLASI:START -->\nsome content\n<!-- CLASI:END -->\n",
        encoding="utf-8",
    )
    uninstall(project)
    # AGENTS.md should be deleted (only CLASI content)
    assert not agents_md.exists()


def test_codex_uninstall_partial_only_skill(project: Path) -> None:
    """uninstall() when only .agents/skills/se/SKILL.md exists raises no errors."""
    skill = project / ".agents" / "skills" / "se" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Skill\n", encoding="utf-8")
    uninstall(project)
    assert not skill.exists()


# ---------------------------------------------------------------------------
# test_clasi_stop_hook_exact_spec_shape — round-trip parse asserts exact spec
# ---------------------------------------------------------------------------


def test_clasi_stop_hook_exact_spec_shape(project: Path) -> None:
    """install() writes hooks.json with the exact Codex spec wrapper structure.

    Round-trips through json.dumps / json.loads and asserts the precise shape:
    {
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {"type": "command",
                         "command": "clasi hook codex-plan-to-todo",
                         "timeout": 30}
                    ]
                }
            ]
        }
    }
    """
    install(project, _MCP_CONFIG)

    hooks_path = project / ".codex" / "hooks.json"
    raw = hooks_path.read_text(encoding="utf-8")
    data = json.loads(raw)  # round-trip through JSON parser

    stop_list = data["hooks"]["Stop"]
    assert len(stop_list) == 1, "Stop list should have exactly one CLASI entry"

    wrapper = stop_list[0]
    assert isinstance(wrapper, dict), "Stop entry must be a dict (wrapper object)"
    assert set(wrapper.keys()) == {"hooks"}, "Wrapper must have only a 'hooks' key"

    inner_hooks = wrapper["hooks"]
    assert isinstance(inner_hooks, list), "'hooks' value must be a list"
    assert len(inner_hooks) == 1, "Inner hooks list must have exactly one handler"

    handler = inner_hooks[0]
    assert handler["type"] == "command", "handler type must be 'command'"
    assert handler["command"] == "clasi hook codex-plan-to-todo"
    assert handler["timeout"] == 30
    assert "args" not in handler, "'args' key must not appear in handler"


# ---------------------------------------------------------------------------
# test_codex_install_replaces_old_flat_format — backward-compat migration
# ---------------------------------------------------------------------------


def test_codex_install_replaces_old_flat_format(project: Path) -> None:
    """install() replaces an existing old flat-format entry, not duplicate it."""
    # Seed hooks.json with the old wrong schema.
    hooks_path = project / ".codex" / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    old_data = {
        "hooks": {
            "Stop": [
                {"command": "clasi", "args": ["hook", "codex-plan-to-todo"]}
            ]
        }
    }
    hooks_path.write_text(json.dumps(old_data, indent=2) + "\n", encoding="utf-8")

    install(project, _MCP_CONFIG)

    data = json.loads(hooks_path.read_text(encoding="utf-8"))
    stop_list = data["hooks"]["Stop"]

    # Old flat entry must be gone.
    assert _CLASI_STOP_HOOK_OLD not in stop_list, "Old flat entry must be removed"
    # New wrapper entry must appear exactly once.
    clasi_entries = [e for e in stop_list if e == _CLASI_STOP_HOOK_WRAPPER]
    assert len(clasi_entries) == 1, "New wrapper entry must appear exactly once"


# ---------------------------------------------------------------------------
# test_codex_uninstall_removes_new_format_entry
# ---------------------------------------------------------------------------


def test_codex_uninstall_removes_new_format_entry(project: Path) -> None:
    """uninstall() removes the new wrapper-format entry from hooks.json."""
    install(project, _MCP_CONFIG)
    uninstall(project)

    hooks_path = project / ".codex" / "hooks.json"
    # File should be deleted since hooks.json contained only CLASI content.
    assert not hooks_path.exists(), "hooks.json should be deleted (was only CLASI content)"


def test_codex_uninstall_handles_old_format_gracefully(project: Path) -> None:
    """uninstall() removes old flat-format entries without error."""
    hooks_path = project / ".codex" / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    old_data = {
        "hooks": {
            "Stop": [
                {"command": "clasi", "args": ["hook", "codex-plan-to-todo"]}
            ]
        }
    }
    hooks_path.write_text(json.dumps(old_data, indent=2) + "\n", encoding="utf-8")

    # Should not raise; old flat entry should be removed.
    uninstall(project)
    assert not hooks_path.exists(), "hooks.json should be deleted after old entry removed"


def test_uninstall_does_not_delete_agents_root_dir(tmp_path: Path) -> None:
    """CLASI uninstall must not remove .agents/ even when another tool has content there."""
    install(tmp_path, _MCP_CONFIG)

    # Simulate another tool using .agents/
    other_file = tmp_path / ".agents" / "other-tool.md"
    other_file.write_text("other tool content", encoding="utf-8")

    uninstall(tmp_path)

    assert (tmp_path / ".agents").is_dir(), ".agents/ must survive CLASI uninstall"
    assert other_file.exists(), "other tool file must survive CLASI uninstall"


def test_uninstall_does_not_raise_when_agents_dir_becomes_empty(tmp_path: Path) -> None:
    """Clean uninstall must not raise even if .agents/ remains as an empty dir."""
    install(tmp_path, _MCP_CONFIG)
    # No extra files — clean state
    uninstall(tmp_path)
    # .agents/ or .agents/skills/ may or may not exist — just no exception raised


# ---------------------------------------------------------------------------
# Sub-agent TOML install / uninstall tests
# ---------------------------------------------------------------------------


def test_install_agents_creates_toml_files(project: Path) -> None:
    """install() creates .codex/agents/<name>.toml for all active agents.

    Verifies:
    - All three TOML files exist after install.
    - Each file round-trips through tomllib.loads without error.
    - Required fields (name, description, developer_instructions) are present.
    - name is a non-empty string.
    - developer_instructions is a non-empty string.
    - description is a string (may be empty).
    """
    install(project, _MCP_CONFIG)

    for agent_name in _ACTIVE_AGENTS:
        toml_path = project / ".codex" / "agents" / f"{agent_name}.toml"
        assert toml_path.exists(), f".codex/agents/{agent_name}.toml must exist after install"

        raw = toml_path.read_text(encoding="utf-8")
        # Round-trip parse — must not raise.
        data = tomllib.loads(raw)

        # Required fields must be present.
        assert "name" in data, f"{agent_name}.toml must contain 'name'"
        assert "description" in data, f"{agent_name}.toml must contain 'description'"
        assert "developer_instructions" in data, (
            f"{agent_name}.toml must contain 'developer_instructions'"
        )

        # Type and non-empty checks.
        assert isinstance(data["name"], str) and data["name"], (
            f"{agent_name}.toml: 'name' must be a non-empty string"
        )
        assert isinstance(data["description"], str), (
            f"{agent_name}.toml: 'description' must be a string"
        )
        assert isinstance(data["developer_instructions"], str) and data["developer_instructions"], (
            f"{agent_name}.toml: 'developer_instructions' must be a non-empty string"
        )

        # developer_instructions must not contain the YAML frontmatter block.
        assert not data["developer_instructions"].startswith("---"), (
            f"{agent_name}.toml: 'developer_instructions' must not start with frontmatter '---'"
        )


def test_uninstall_agents_removes_toml_files(project: Path) -> None:
    """install then uninstall removes all .codex/agents/<name>.toml files.

    Also verifies the .codex/agents/ directory is removed when empty.
    """
    install(project, _MCP_CONFIG)

    # Confirm files exist before uninstall.
    for agent_name in _ACTIVE_AGENTS:
        assert (project / ".codex" / "agents" / f"{agent_name}.toml").exists()

    uninstall(project)

    for agent_name in _ACTIVE_AGENTS:
        toml_path = project / ".codex" / "agents" / f"{agent_name}.toml"
        assert not toml_path.exists(), (
            f".codex/agents/{agent_name}.toml must be removed by uninstall"
        )

    # Directory should be gone when empty.
    agents_dir = project / ".codex" / "agents"
    assert not agents_dir.exists(), ".codex/agents/ must be removed when empty after uninstall"


def test_uninstall_agents_preserves_user_files(project: Path) -> None:
    """uninstall() does not remove user-added files in .codex/agents/."""
    install(project, _MCP_CONFIG)

    # Add a user file alongside the CLASI-owned TOML files.
    agents_dir = project / ".codex" / "agents"
    user_file = agents_dir / "my-custom-agent.toml"
    user_file.write_text(
        'name = "my-custom-agent"\ndescription = "custom"\ndeveloper_instructions = "do stuff"\n',
        encoding="utf-8",
    )

    uninstall(project)

    # CLASI files must be gone.
    for agent_name in _ACTIVE_AGENTS:
        toml_path = agents_dir / f"{agent_name}.toml"
        assert not toml_path.exists(), (
            f".codex/agents/{agent_name}.toml must be removed by uninstall"
        )

    # User file must still be present.
    assert user_file.exists(), "User-added .codex/agents/my-custom-agent.toml must be preserved"

    # Directory must still exist (user file is in it).
    assert agents_dir.exists(), ".codex/agents/ must not be removed when user files remain"


# ---------------------------------------------------------------------------
# Nested AGENTS.md rule file tests
# ---------------------------------------------------------------------------


def test_install_rules_creates_agents_md_files(project: Path) -> None:
    """install() creates .clasi/AGENTS.md and clasi/AGENTS.md with correct content.

    Verifies:
    - Both files exist after install.
    - .clasi/AGENTS.md contains SE process content (MCP server mention).
    - clasi/AGENTS.md contains source-code rule content (ticket status mention).
    - Neither file contains Claude-Code-specific metadata (YAML frontmatter).
    """
    install(project, _MCP_CONFIG)

    dot_clasi_md = project / ".clasi" / "AGENTS.md"
    assert dot_clasi_md.exists(), ".clasi/AGENTS.md should exist after install"
    docs_content = dot_clasi_md.read_text(encoding="utf-8")
    assert "MCP" in docs_content, ".clasi/AGENTS.md must mention MCP server"
    assert "CLASI MCP" in docs_content, ".clasi/AGENTS.md must reference CLASI MCP tools"
    # No YAML frontmatter (Claude-specific metadata).
    assert not docs_content.startswith("---"), (
        ".clasi/AGENTS.md must not start with YAML frontmatter"
    )

    clasi_src_md = project / "clasi" / "AGENTS.md"
    assert clasi_src_md.exists(), "clasi/AGENTS.md should exist after install"
    src_content = clasi_src_md.read_text(encoding="utf-8")
    assert "in-progress" in src_content, (
        "clasi/AGENTS.md must mention ticket in-progress status"
    )
    assert not src_content.startswith("---"), (
        "clasi/AGENTS.md must not start with YAML frontmatter"
    )

    # Content must match the builder output exactly.
    assert docs_content == _build_clasi_dir_content()
    assert src_content == _CLASI_SRC_RULES


def test_uninstall_rules_removes_files(project: Path) -> None:
    """install then uninstall removes both nested AGENTS.md rule files."""
    install(project, _MCP_CONFIG)

    dot_clasi_md = project / ".clasi" / "AGENTS.md"
    clasi_src_md = project / "clasi" / "AGENTS.md"

    # Confirm files exist before uninstall.
    assert dot_clasi_md.exists()
    assert clasi_src_md.exists()

    uninstall(project)

    assert not dot_clasi_md.exists(), (
        ".clasi/AGENTS.md must be removed by uninstall"
    )
    assert not clasi_src_md.exists(), "clasi/AGENTS.md must be removed by uninstall"


def test_uninstall_rules_no_error_if_missing(project: Path) -> None:
    """uninstall() on a directory with no nested rule files raises no errors."""
    # Neither .clasi/AGENTS.md nor clasi/AGENTS.md exists — must not raise.
    uninstall(project)


# ---------------------------------------------------------------------------
# Global rules block tests (ticket 006)
# ---------------------------------------------------------------------------


def test_global_rules_content_present_after_install(tmp_path: Path) -> None:
    """Root AGENTS.md's single CLASI block contains entry point + global rules."""
    install(tmp_path, _MCP_CONFIG)

    content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "<!-- CLASI:START -->" in content
    assert "<!-- CLASI:END -->" in content
    # Rule content is present (from MCP_REQUIRED_BODY and GIT_COMMITS_BODY).
    assert "get_version" in content or "MCP server" in content
    assert "commit" in content.lower() or "git" in content.lower()
    # Single combined block — no separate :RULES marker pair.
    assert "<!-- CLASI:RULES:START -->" not in content
    assert "<!-- CLASI:RULES:END -->" not in content


def test_global_rules_stripped_on_uninstall(tmp_path: Path) -> None:
    """Uninstall removes the entire CLASI block including rule content."""
    install(tmp_path, _MCP_CONFIG)
    uninstall(tmp_path)

    # After a clean install+uninstall, AGENTS.md should be deleted (only CLASI content).
    agents_md = tmp_path / "AGENTS.md"
    if agents_md.exists():
        content = agents_md.read_text(encoding="utf-8")
        assert "<!-- CLASI:START -->" not in content
        assert "<!-- CLASI:END -->" not in content


def test_uninstall_preserves_user_content_around_clasi_block(
    tmp_path: Path,
) -> None:
    """User content outside the CLASI block survives uninstall."""
    user_content = "# My custom instructions\n\nDo things my way.\n"
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text(user_content, encoding="utf-8")

    install(tmp_path, _MCP_CONFIG)
    after_install = agents_md.read_text(encoding="utf-8")
    assert "<!-- CLASI:START -->" in after_install
    assert "My custom instructions" in after_install

    uninstall(tmp_path)

    # AGENTS.md survives (user content is present); CLASI block is gone.
    assert agents_md.exists()
    content = agents_md.read_text(encoding="utf-8")
    assert "My custom instructions" in content
    assert "Do things my way" in content
    assert "<!-- CLASI:START -->" not in content
    assert "<!-- CLASI:END -->" not in content


def test_clasi_block_round_trip_no_duplication(tmp_path: Path) -> None:
    """install -> uninstall -> install produces exactly one CLASI block, no duplication."""
    install(tmp_path, _MCP_CONFIG)
    uninstall(tmp_path)
    install(tmp_path, _MCP_CONFIG)

    content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert content.count("<!-- CLASI:START -->") == 1
    assert content.count("<!-- CLASI:END -->") == 1


def test_clasi_block_install_idempotent(tmp_path: Path) -> None:
    """Running install() twice produces no duplication in the CLASI block."""
    install(tmp_path, _MCP_CONFIG)
    install(tmp_path, _MCP_CONFIG)

    content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert content.count("<!-- CLASI:START -->") == 1
    assert content.count("<!-- CLASI:END -->") == 1


# ---------------------------------------------------------------------------
# test_codex_install_end_to_end — canonical round-trip correctness check
# ---------------------------------------------------------------------------


def test_codex_install_end_to_end(tmp_path: Path) -> None:
    """End-to-end install correctness: round-trip parse every emitted file.

    Calls install() against a fresh directory and validates each artifact
    via its actual spec parser (tomllib or json.loads), not substring matching.
    This is the canonical regression guard — it catches any change that
    silently breaks another artifact's shape.
    """
    mcp_config = {"command": "clasi", "args": ["mcp"]}
    install(tmp_path, mcp_config=mcp_config)

    # ------------------------------------------------------------------
    # .codex/config.toml — parse with tomllib, assert mcp_servers.clasi
    # ------------------------------------------------------------------
    config_path = tmp_path / ".codex" / "config.toml"
    assert config_path.exists(), ".codex/config.toml must exist after install"
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert "mcp_servers" in config, "config.toml must have [mcp_servers] table"
    assert "clasi" in config["mcp_servers"], "config.toml must have [mcp_servers.clasi]"
    assert config["mcp_servers"]["clasi"] == mcp_config, (
        "mcp_servers.clasi must equal the supplied mcp_config exactly"
    )

    # ------------------------------------------------------------------
    # .codex/hooks.json — parse with json.loads, assert wrapper Stop hook
    # ------------------------------------------------------------------
    hooks_path = tmp_path / ".codex" / "hooks.json"
    assert hooks_path.exists(), ".codex/hooks.json must exist after install"
    hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
    assert "hooks" in hooks, "hooks.json must have top-level 'hooks' key"
    assert "Stop" in hooks["hooks"], "hooks.json must have hooks.Stop list"
    stop_list = hooks["hooks"]["Stop"]
    assert len(stop_list) >= 1, "Stop list must have at least one entry"
    wrapper = stop_list[0]
    assert isinstance(wrapper, dict), "First Stop entry must be a dict (wrapper)"
    assert "hooks" in wrapper, "Wrapper must have a 'hooks' key"
    inner_list = wrapper["hooks"]
    assert isinstance(inner_list, list) and len(inner_list) >= 1, (
        "Wrapper hooks must be a non-empty list"
    )
    stop_hook = inner_list[0]
    assert stop_hook["type"] == "command", "Handler type must be 'command'"
    assert stop_hook["command"] == "clasi hook codex-plan-to-todo", (
        "Handler command must be 'clasi hook codex-plan-to-todo'"
    )
    assert "timeout" in stop_hook, "Handler must have 'timeout' key"
    assert "args" not in stop_hook, "'args' key must be absent from handler"

    # ------------------------------------------------------------------
    # .codex/agents/team-lead.toml — parse with tomllib, assert required fields
    # ------------------------------------------------------------------
    agent_path = tmp_path / ".codex" / "agents" / "team-lead.toml"
    assert agent_path.exists(), ".codex/agents/team-lead.toml must exist after install"
    agent = tomllib.loads(agent_path.read_text(encoding="utf-8"))
    assert "name" in agent, "team-lead.toml must have 'name'"
    assert isinstance(agent["name"], str) and agent["name"], (
        "'name' must be a non-empty string"
    )
    assert "description" in agent, "team-lead.toml must have 'description'"
    assert isinstance(agent["description"], str), "'description' must be a string"
    assert "developer_instructions" in agent, (
        "team-lead.toml must have 'developer_instructions'"
    )
    assert isinstance(agent["developer_instructions"], str) and agent["developer_instructions"], (
        "'developer_instructions' must be a non-empty string"
    )

    # ------------------------------------------------------------------
    # AGENTS.md (root) — marker block present; /se line absent
    # ------------------------------------------------------------------
    agents_md_path = tmp_path / "AGENTS.md"
    assert agents_md_path.exists(), "AGENTS.md must exist after install"
    agents_md = agents_md_path.read_text(encoding="utf-8")
    assert "<!-- CLASI:START -->" in agents_md, "AGENTS.md must contain CLASI marker start"
    assert "<!-- CLASI:END -->" in agents_md, "AGENTS.md must contain CLASI marker end"
    assert "CLASI" in agents_md, "AGENTS.md must mention CLASI"
    assert "run `/se`" not in agents_md, (
        "AGENTS.md must not contain the 'run `/se`' dispatcher line (ticket 003)"
    )
    assert "Available skills: run" not in agents_md, (
        "AGENTS.md must not contain the 'Available skills: run /se for a list' line"
    )

    # ------------------------------------------------------------------
    # .clasi/AGENTS.md — MCP content present
    # ------------------------------------------------------------------
    dot_clasi_path = tmp_path / ".clasi" / "AGENTS.md"
    assert dot_clasi_path.exists(), ".clasi/AGENTS.md must exist after install"
    docs_rules = dot_clasi_path.read_text(encoding="utf-8")
    assert "MCP" in docs_rules or "clasi" in docs_rules.lower(), (
        ".clasi/AGENTS.md must contain MCP or CLASI MCP reference"
    )

    # ------------------------------------------------------------------
    # clasi/AGENTS.md — in-progress or ticket content present
    # ------------------------------------------------------------------
    src_rules_path = tmp_path / "clasi" / "AGENTS.md"
    assert src_rules_path.exists(), "clasi/AGENTS.md must exist after install"
    src_rules = src_rules_path.read_text(encoding="utf-8")
    assert "ticket" in src_rules.lower() or "in-progress" in src_rules, (
        "clasi/AGENTS.md must mention 'ticket' or 'in-progress'"
    )

    # ------------------------------------------------------------------
    # .agents/skills/<name>/SKILL.md (25 skills) — all present with frontmatter
    # ------------------------------------------------------------------
    from clasi.platforms.codex import _PLUGIN_DIR

    plugin_skills = _PLUGIN_DIR / "skills"
    expected_skills = [
        d.name for d in sorted(plugin_skills.iterdir())
        if d.is_dir() and (d / "SKILL.md").exists()
    ]
    assert len(expected_skills) == 25, (
        f"Expected 25 skills in plugin, found {len(expected_skills)}"
    )
    for skill_name in expected_skills:
        skill_path = tmp_path / ".agents" / "skills" / skill_name / "SKILL.md"
        assert skill_path.exists(), (
            f".agents/skills/{skill_name}/SKILL.md must exist after install"
        )
        skill_text = skill_path.read_text(encoding="utf-8")
        assert skill_text.startswith("---"), (
            f".agents/skills/{skill_name}/SKILL.md must have YAML frontmatter"
        )
        # Parse frontmatter: lines between the first pair of --- delimiters.
        lines = skill_text.splitlines()
        end_fm = next(
            (i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
            None,
        )
        assert end_fm is not None, (
            f".agents/skills/{skill_name}/SKILL.md: YAML frontmatter not closed"
        )
        fm_block = "\n".join(lines[1:end_fm])
        assert "name:" in fm_block, (
            f".agents/skills/{skill_name}/SKILL.md frontmatter must have 'name:'"
        )
        assert "description:" in fm_block, (
            f".agents/skills/{skill_name}/SKILL.md frontmatter must have 'description:'"
        )


# ---------------------------------------------------------------------------
# Ticket 007: full clasi-artifacts content + .clasi/issues/AGENTS.md
# ---------------------------------------------------------------------------


def test_docs_clasi_agents_md_has_full_clasi_artifacts_content(tmp_path: Path) -> None:
    """.clasi/AGENTS.md must contain the active-sprint check and phase check."""
    install(tmp_path, _MCP_CONFIG)

    content = (tmp_path / ".clasi" / "AGENTS.md").read_text(encoding="utf-8")
    # The full clasi-artifacts rule includes these concepts.
    assert "active sprint" in content.lower() or "list_sprints" in content
    assert "phase" in content.lower() or "ticketing" in content.lower()
    assert "MCP" in content or "mcp" in content.lower()


def test_docs_clasi_todo_agents_md_created(tmp_path: Path) -> None:
    """.clasi/issues/AGENTS.md must be written by codex install."""
    install(tmp_path, _MCP_CONFIG)

    issues_agents = tmp_path / ".clasi" / "issues" / "AGENTS.md"
    assert issues_agents.exists(), ".clasi/issues/AGENTS.md must exist after install"
    content = issues_agents.read_text(encoding="utf-8")
    assert "todo" in content.lower() or "move_todo_to_done" in content


def test_docs_clasi_todo_agents_md_removed_on_uninstall(tmp_path: Path) -> None:
    """.clasi/issues/AGENTS.md must be removed on uninstall."""
    install(tmp_path, _MCP_CONFIG)
    uninstall(tmp_path)
    assert not (tmp_path / ".clasi" / "issues" / "AGENTS.md").exists(), (
        ".clasi/issues/AGENTS.md must be removed by uninstall"
    )


# ---------------------------------------------------------------------------
# Ticket 008: comprehensive end-to-end footprint test for all AGENTS.md files
# ---------------------------------------------------------------------------


def test_codex_install_full_agents_md_footprint(tmp_path: Path) -> None:
    """After codex.install(), all four AGENTS.md files exist at correct paths
    with correct content, and root AGENTS.md has both CLASI marker blocks.

    This is the canonical regression guard — if any future ticket breaks the
    install footprint, this test fails immediately.
    """
    install(tmp_path, _MCP_CONFIG)

    # --- Root AGENTS.md: entry-point block + global-rules block ---
    root_agents = tmp_path / "AGENTS.md"
    assert root_agents.exists(), "root AGENTS.md must exist after codex install"
    root_content = root_agents.read_text(encoding="utf-8")

    assert "<!-- CLASI:START -->" in root_content, "CLASI block start must be present"
    assert "<!-- CLASI:END -->" in root_content, "CLASI block end must be present"

    # Block must not be duplicated.
    assert root_content.count("<!-- CLASI:START -->") == 1, (
        "root AGENTS.md: CLASI:START must appear exactly once (no duplication)"
    )
    assert root_content.count("<!-- CLASI:END -->") == 1, (
        "root AGENTS.md: CLASI:END must appear exactly once (no duplication)"
    )

    # Single block — no separate :RULES marker pair.
    assert "<!-- CLASI:RULES:START -->" not in root_content
    assert "<!-- CLASI:RULES:END -->" not in root_content

    # Key rule content from MCP_REQUIRED_BODY and GIT_COMMITS_BODY must be present.
    assert "get_version" in root_content or "MCP server" in root_content, (
        "root AGENTS.md: mcp-required rule content (get_version / MCP server) must be present"
    )
    assert "commit" in root_content.lower() or "git" in root_content.lower(), (
        "root AGENTS.md: git-commits rule content (commit / git) must be present"
    )

    # --- .clasi/AGENTS.md: full clasi-artifacts content ---
    dot_clasi_agents = tmp_path / ".clasi" / "AGENTS.md"
    assert dot_clasi_agents.exists(), ".clasi/AGENTS.md must exist after codex install"
    docs_content = dot_clasi_agents.read_text(encoding="utf-8")

    # Active-sprint check.
    assert "list_sprints" in docs_content or "active sprint" in docs_content.lower(), (
        ".clasi/AGENTS.md: must contain active-sprint check (list_sprints or 'active sprint')"
    )
    # Phase check.
    assert "phase" in docs_content.lower() or "ticketing" in docs_content.lower(), (
        ".clasi/AGENTS.md: must contain phase check ('phase' or 'ticketing')"
    )
    # MCP-tools-only instruction.
    assert "MCP" in docs_content or "mcp" in docs_content.lower(), (
        ".clasi/AGENTS.md: must contain MCP tools instruction"
    )

    # --- .clasi/issues/AGENTS.md: issues-dir content ---
    issues_agents = tmp_path / ".clasi" / "issues" / "AGENTS.md"
    assert issues_agents.exists(), ".clasi/issues/AGENTS.md must exist after codex install"
    todo_content = issues_agents.read_text(encoding="utf-8")

    assert "move_todo_to_done" in todo_content or "todo" in todo_content.lower(), (
        ".clasi/issues/AGENTS.md: must contain issues-dir rule content"
    )

    # --- clasi/AGENTS.md: source-code content ---
    clasi_agents = tmp_path / "clasi" / "AGENTS.md"
    assert clasi_agents.exists(), "clasi/AGENTS.md must exist after codex install"
    clasi_content = clasi_agents.read_text(encoding="utf-8")

    assert "in-progress" in clasi_content or "ticket" in clasi_content.lower(), (
        "clasi/AGENTS.md: must contain source-code rule content (in-progress / ticket)"
    )


def test_codex_uninstall_removes_all_agents_md_files(tmp_path: Path) -> None:
    """After codex.uninstall(), all nested AGENTS.md files are removed and
    the root AGENTS.md has no remaining CLASI blocks.
    """
    install(tmp_path, _MCP_CONFIG)
    uninstall(tmp_path)

    # Nested files must be gone.
    assert not (tmp_path / ".clasi" / "AGENTS.md").exists(), (
        ".clasi/AGENTS.md must be removed by uninstall"
    )
    assert not (tmp_path / ".clasi" / "issues" / "AGENTS.md").exists(), (
        ".clasi/issues/AGENTS.md must be removed by uninstall"
    )
    assert not (tmp_path / "clasi" / "AGENTS.md").exists(), (
        "clasi/AGENTS.md must be removed by uninstall"
    )

    # Root AGENTS.md: either deleted or stripped of the CLASI block.
    root_agents = tmp_path / "AGENTS.md"
    if root_agents.exists():
        content = root_agents.read_text(encoding="utf-8")
        assert "<!-- CLASI:START -->" not in content, (
            "root AGENTS.md: CLASI block must be stripped on uninstall"
        )
        assert "<!-- CLASI:END -->" not in content


def test_codex_install_round_trip_no_duplication(tmp_path: Path) -> None:
    """Install -> uninstall -> re-install produces the same file state as the first
    install.  No block duplication in root AGENTS.md and all four AGENTS.md files
    are present after re-install.
    """
    # First install.
    install(tmp_path, _MCP_CONFIG)
    uninstall(tmp_path)

    # Re-install.
    install(tmp_path, _MCP_CONFIG)

    # Root AGENTS.md must have exactly one CLASI block.
    root_agents = tmp_path / "AGENTS.md"
    assert root_agents.exists(), "root AGENTS.md must exist after re-install"
    content = root_agents.read_text(encoding="utf-8")

    assert content.count("<!-- CLASI:START -->") == 1, (
        "root AGENTS.md: CLASI block must not be duplicated after re-install"
    )
    assert content.count("<!-- CLASI:END -->") == 1, (
        "root AGENTS.md: CLASI block end must not be duplicated after re-install"
    )

    # All nested AGENTS.md files must exist after re-install.
    assert (tmp_path / ".clasi" / "AGENTS.md").exists(), (
        ".clasi/AGENTS.md must exist after re-install"
    )
    assert (tmp_path / ".clasi" / "issues" / "AGENTS.md").exists(), (
        ".clasi/issues/AGENTS.md must exist after re-install"
    )
    assert (tmp_path / "clasi" / "AGENTS.md").exists(), (
        "clasi/AGENTS.md must exist after re-install"
    )
