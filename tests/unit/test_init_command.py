"""Tests for claude_agent_skills.init_command module."""

import json

import pytest

from claude_agent_skills.init_command import (
    run_init,
    MCP_CONFIG,
    VSCODE_MCP_CONFIG,
    _SE_SKILL_PATH,
    _AGENTS_SECTION_PATH,
    _AGENTS_SECTION_START,
    _AGENTS_SECTION_END,
    _CLAUDE_MD_PATH,
)


@pytest.fixture
def target_dir(tmp_path):
    """Return a temp directory to use as init target."""
    return tmp_path / "target_repo"


class TestRunInit:
    def test_creates_se_skill(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        skill = target_dir / ".claude" / "skills" / "se" / "SKILL.md"
        assert skill.exists()
        source = _SE_SKILL_PATH.read_text(encoding="utf-8")
        assert skill.read_text(encoding="utf-8") == source

    def test_se_skill_references_mcp(self):
        source = _SE_SKILL_PATH.read_text(encoding="utf-8")
        assert "get_skill_definition" in source
        assert "get_se_overview" in source

    def test_se_skill_idempotent(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))
        run_init(str(target_dir))

        skill = target_dir / ".claude" / "skills" / "se" / "SKILL.md"
        source = _SE_SKILL_PATH.read_text(encoding="utf-8")
        assert skill.read_text(encoding="utf-8") == source

    def test_does_not_create_old_skill_stubs(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        skills_dir = target_dir / ".claude" / "skills"
        for old_name in ["todo", "next", "status", "project-initiation",
                         "report", "ghtodo"]:
            assert not (skills_dir / old_name).exists()

    def test_does_not_create_rule_files(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        rules_dir = target_dir / ".claude" / "rules"
        assert not rules_dir.exists()

    def test_does_not_create_copilot_mirror(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        copilot_dir = target_dir / ".github" / "copilot" / "instructions"
        assert not copilot_dir.exists()

    def test_does_not_create_codex_symlink(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        codex = target_dir / ".codex"
        assert not codex.exists()

    def test_does_not_modify_gitignore(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        gitignore = target_dir / ".gitignore"
        assert not gitignore.exists()

    def test_preserves_existing_gitignore(self, target_dir):
        target_dir.mkdir()
        (target_dir / ".gitignore").write_text("node_modules/\n",
                                               encoding="utf-8")
        run_init(str(target_dir))

        content = (target_dir / ".gitignore").read_text(encoding="utf-8")
        assert content == "node_modules/\n"

    def test_creates_mcp_json(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        mcp_json = target_dir / ".mcp.json"
        assert mcp_json.exists()

        data = json.loads(mcp_json.read_text(encoding="utf-8"))
        assert data["mcpServers"]["clasi"] == MCP_CONFIG["clasi"]

    def test_idempotent(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))
        run_init(str(target_dir))

        mcp_json = target_dir / ".mcp.json"
        data = json.loads(mcp_json.read_text(encoding="utf-8"))
        assert data["mcpServers"]["clasi"] == MCP_CONFIG["clasi"]

    def test_merges_existing_mcp_json(self, target_dir):
        target_dir.mkdir()
        mcp_json = target_dir / ".mcp.json"
        existing = {"mcpServers": {"other": {"command": "other"}}}
        mcp_json.write_text(json.dumps(existing), encoding="utf-8")

        run_init(str(target_dir))

        data = json.loads(mcp_json.read_text(encoding="utf-8"))
        assert data["mcpServers"]["other"] == {"command": "other"}
        assert data["mcpServers"]["clasi"] == MCP_CONFIG["clasi"]

    def test_adds_permission_to_settings(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        settings_path = target_dir / ".claude" / "settings.local.json"
        assert settings_path.exists()
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "mcp__clasi__*" in data["permissions"]["allow"]

    def test_settings_idempotent(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))
        run_init(str(target_dir))

        settings_path = target_dir / ".claude" / "settings.local.json"
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert data["permissions"]["allow"].count("mcp__clasi__*") == 1

    def test_settings_preserves_existing(self, target_dir):
        target_dir.mkdir()
        settings_path = target_dir / ".claude" / "settings.local.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {"permissions": {"allow": ["Bash(*)"]}, "other": "kept"}
        settings_path.write_text(json.dumps(existing), encoding="utf-8")

        run_init(str(target_dir))

        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "Bash(*)" in data["permissions"]["allow"]
        assert "mcp__clasi__*" in data["permissions"]["allow"]
        assert data["other"] == "kept"

    def test_creates_vscode_mcp_json(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        vscode_mcp = target_dir / ".vscode" / "mcp.json"
        assert vscode_mcp.exists()
        data = json.loads(vscode_mcp.read_text(encoding="utf-8"))
        assert data["servers"]["clasi"] == VSCODE_MCP_CONFIG["clasi"]

    def test_vscode_mcp_json_idempotent(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))
        run_init(str(target_dir))

        vscode_mcp = target_dir / ".vscode" / "mcp.json"
        data = json.loads(vscode_mcp.read_text(encoding="utf-8"))
        assert data["servers"]["clasi"] == VSCODE_MCP_CONFIG["clasi"]

    def test_vscode_mcp_json_merges_existing(self, target_dir):
        target_dir.mkdir()
        vscode_dir = target_dir / ".vscode"
        vscode_dir.mkdir()
        existing = {"servers": {"other": {"type": "stdio", "command": "other"}}}
        (vscode_dir / "mcp.json").write_text(json.dumps(existing),
                                             encoding="utf-8")

        run_init(str(target_dir))

        data = json.loads((vscode_dir / "mcp.json").read_text(encoding="utf-8"))
        assert data["servers"]["other"] == {"type": "stdio", "command": "other"}
        assert data["servers"]["clasi"] == VSCODE_MCP_CONFIG["clasi"]


class TestAgentsMd:
    def test_creates_agents_md_when_missing(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        agents_md = target_dir / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text(encoding="utf-8")
        assert _AGENTS_SECTION_START in content
        assert _AGENTS_SECTION_END in content
        assert "CLASI Software Engineering Process" in content

    def test_appends_to_existing_agents_md(self, target_dir):
        target_dir.mkdir()
        existing = "# My Project\n\nThis is my project.\n"
        (target_dir / "AGENTS.md").write_text(existing, encoding="utf-8")

        run_init(str(target_dir))

        content = (target_dir / "AGENTS.md").read_text(encoding="utf-8")
        assert content.startswith("# My Project")
        assert "This is my project." in content
        assert _AGENTS_SECTION_START in content
        assert "CLASI Software Engineering Process" in content

    def test_updates_existing_clasi_section(self, target_dir):
        target_dir.mkdir()
        old_section = (
            f"{_AGENTS_SECTION_START}\n"
            "## Old CLASI Section\n\nOld content.\n"
            f"{_AGENTS_SECTION_END}"
        )
        existing = f"# My Project\n\n{old_section}\n\n## Other Section\n"
        (target_dir / "AGENTS.md").write_text(existing, encoding="utf-8")

        run_init(str(target_dir))

        content = (target_dir / "AGENTS.md").read_text(encoding="utf-8")
        assert "Old content." not in content
        assert "CLASI Software Engineering Process" in content
        assert "## Other Section" in content
        assert content.count(_AGENTS_SECTION_START) == 1

    def test_agents_md_idempotent(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))
        content_after_first = (target_dir / "AGENTS.md").read_text(
            encoding="utf-8")

        run_init(str(target_dir))
        content_after_second = (target_dir / "AGENTS.md").read_text(
            encoding="utf-8")

        assert content_after_first == content_after_second

    def test_agents_section_has_process_structure(self):
        section = _AGENTS_SECTION_PATH.read_text(encoding="utf-8")
        assert "Project initiation" in section
        assert "Sprint lifecycle" in section
        assert "Create sprint" in section
        assert "Architecture review" in section
        assert "Create tickets" in section
        assert "Execute tickets" in section
        assert "Close sprint" in section

    def test_agents_section_has_behavioral_rules(self):
        section = _AGENTS_SECTION_PATH.read_text(encoding="utf-8")
        assert "Pre-Flight Check" in section
        assert "CLASI Skills First" in section
        assert "Stop and Report" in section
        assert "list_skills()" in section
        assert "list_sprints()" in section

    def test_agents_section_has_scold_detection(self):
        section = _AGENTS_SECTION_PATH.read_text(encoding="utf-8")
        assert "Stakeholder Corrections" in section
        assert "self-reflect" in section

    def test_agents_section_has_ticket_completion_rules(self):
        section = _AGENTS_SECTION_PATH.read_text(encoding="utf-8")
        assert "move_ticket_to_done" in section
        assert "close_sprint" in section
        assert "Finishing the code is NOT finishing the ticket" in section

    def test_agents_section_has_sprint_closure_rules(self):
        section = _AGENTS_SECTION_PATH.read_text(encoding="utf-8")
        assert "Never merge a sprint branch without archiving" in section
        assert "Never leave a sprint branch dangling" in section


class TestClaudeMd:
    def test_creates_claude_md_when_missing(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        claude_md = target_dir / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text(encoding="utf-8")
        assert "@AGENTS.md" in content

    def test_does_not_overwrite_existing_claude_md(self, target_dir):
        target_dir.mkdir()
        existing = "# My Project\n\nCustom CLAUDE.md content.\n"
        (target_dir / "CLAUDE.md").write_text(existing, encoding="utf-8")

        run_init(str(target_dir))

        content = (target_dir / "CLAUDE.md").read_text(encoding="utf-8")
        assert content == existing

    def test_claude_md_idempotent(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))
        content_after_first = (target_dir / "CLAUDE.md").read_text(
            encoding="utf-8")

        run_init(str(target_dir))
        content_after_second = (target_dir / "CLAUDE.md").read_text(
            encoding="utf-8")

        assert content_after_first == content_after_second

    def test_claude_md_template_references_agents(self):
        source = _CLAUDE_MD_PATH.read_text(encoding="utf-8")
        assert "@AGENTS.md" in source
