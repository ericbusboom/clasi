"""Tests for claude_agent_skills.init_command module."""

import json

import pytest

from claude_agent_skills.init_command import (
    run_init,
    MCP_CONFIG,
    HOOKS_CONFIG,
    RULES,
    VSCODE_MCP_CONFIG,
    _SE_SKILL_PATH,
    _AGENTS_SECTION_PATH,
    _AGENTS_SECTION_START,
    _AGENTS_SECTION_END,
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

    def test_creates_rule_files(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        rules_dir = target_dir / ".claude" / "rules"
        assert rules_dir.exists()
        for filename in RULES:
            assert (rules_dir / filename).exists()

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

    def test_does_not_create_agents_md(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        agents_md = target_dir / "AGENTS.md"
        assert not agents_md.exists()

    def test_does_not_modify_existing_agents_md(self, target_dir):
        target_dir.mkdir()
        existing = "# My Agents\n\nCustom content.\n"
        (target_dir / "AGENTS.md").write_text(existing, encoding="utf-8")

        run_init(str(target_dir))

        content = (target_dir / "AGENTS.md").read_text(encoding="utf-8")
        assert content == existing


class TestClaudeMd:
    def test_creates_claude_md_with_clasi_block(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        claude_md = target_dir / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text(encoding="utf-8")
        assert _AGENTS_SECTION_START in content
        assert _AGENTS_SECTION_END in content
        assert "CLASI Software Engineering Process" in content
        assert "@AGENTS.md" not in content

    def test_appends_to_existing_claude_md(self, target_dir):
        target_dir.mkdir()
        existing = "# My Project\n\nThis is my project.\n"
        (target_dir / "CLAUDE.md").write_text(existing, encoding="utf-8")

        run_init(str(target_dir))

        content = (target_dir / "CLAUDE.md").read_text(encoding="utf-8")
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
        (target_dir / "CLAUDE.md").write_text(existing, encoding="utf-8")

        run_init(str(target_dir))

        content = (target_dir / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Old content." not in content
        assert "CLASI Software Engineering Process" in content
        assert "## Other Section" in content
        assert content.count(_AGENTS_SECTION_START) == 1

    def test_claude_md_idempotent(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))
        content_after_first = (target_dir / "CLAUDE.md").read_text(
            encoding="utf-8")

        run_init(str(target_dir))
        content_after_second = (target_dir / "CLAUDE.md").read_text(
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


class TestHooksConfig:
    def test_init_creates_hooks_in_settings(self, target_dir):
        """Init creates UserPromptSubmit hook in settings.json (shared)."""
        target_dir.mkdir()
        run_init(str(target_dir))

        settings_path = target_dir / ".claude" / "settings.json"
        assert settings_path.exists()
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "hooks" in data
        assert "UserPromptSubmit" in data["hooks"]
        entries = data["hooks"]["UserPromptSubmit"]
        assert len(entries) == 1
        # Correct matcher+hooks format
        assert entries[0]["matcher"] == ""
        assert len(entries[0]["hooks"]) == 1
        assert entries[0]["hooks"][0]["type"] == "command"
        assert "get_se_overview()" in entries[0]["hooks"][0]["command"]

    def test_hooks_idempotent(self, target_dir):
        """Running init twice does not duplicate the hook entry."""
        target_dir.mkdir()
        run_init(str(target_dir))
        run_init(str(target_dir))

        settings_path = target_dir / ".claude" / "settings.json"
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        entries = data["hooks"]["UserPromptSubmit"]
        assert len(entries) == 1

    def test_hooks_preserve_existing_settings(self, target_dir):
        """Hook installation preserves existing keys in settings.json."""
        target_dir.mkdir()
        settings_path = target_dir / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {
            "other": "kept",
        }
        settings_path.write_text(json.dumps(existing), encoding="utf-8")

        run_init(str(target_dir))

        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert data["other"] == "kept"
        assert "hooks" in data
        entries = data["hooks"]["UserPromptSubmit"]
        assert len(entries) == 1
        assert entries[0] == HOOKS_CONFIG["UserPromptSubmit"][0]

    def test_hooks_correct_format(self, target_dir):
        """Hook entry uses matcher+hooks format per Claude Code spec."""
        target_dir.mkdir()
        run_init(str(target_dir))

        settings_path = target_dir / ".claude" / "settings.json"
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        entries = data["hooks"]["UserPromptSubmit"]
        assert entries == HOOKS_CONFIG["UserPromptSubmit"]
        # Verify structure
        assert "matcher" in entries[0]
        assert "hooks" in entries[0]
        assert isinstance(entries[0]["hooks"], list)

    def test_hooks_preserve_existing_hooks(self, target_dir):
        """Hook installation preserves other existing hook entries."""
        target_dir.mkdir()
        settings_path = target_dir / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        existing_entry = {
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": "echo 'other hook'"}],
        }
        existing = {
            "hooks": {
                "UserPromptSubmit": [existing_entry],
                "PreToolUse": [
                    {"matcher": "", "hooks": [{"type": "command", "command": "echo pre"}]}
                ],
            }
        }
        settings_path.write_text(json.dumps(existing), encoding="utf-8")

        run_init(str(target_dir))

        data = json.loads(settings_path.read_text(encoding="utf-8"))
        # Other hook event types are preserved
        assert len(data["hooks"]["PreToolUse"]) == 1
        # Existing UserPromptSubmit entry is preserved alongside CLASI entry
        ups_entries = data["hooks"]["UserPromptSubmit"]
        assert len(ups_entries) == 2
        assert existing_entry in ups_entries
        assert HOOKS_CONFIG["UserPromptSubmit"][0] in ups_entries


class TestRules:
    def test_init_creates_all_rule_files(self, target_dir):
        """Init creates all CLASI rule files."""
        target_dir.mkdir()
        run_init(str(target_dir))

        rules_dir = target_dir / ".claude" / "rules"
        expected = {"mcp-required.md", "clasi-artifacts.md", "source-code.md",
                    "todo-dir.md", "git-commits.md"}
        created = {f.name for f in rules_dir.iterdir() if f.is_file()}
        assert expected == created

    def test_rule_content_matches_constants(self, target_dir):
        """Each rule file contains the exact content from the RULES dict."""
        target_dir.mkdir()
        run_init(str(target_dir))

        rules_dir = target_dir / ".claude" / "rules"
        for filename, expected_content in RULES.items():
            actual = (rules_dir / filename).read_text(encoding="utf-8")
            assert actual == expected_content

    def test_rules_have_paths_frontmatter(self, target_dir):
        """Each rule file has YAML frontmatter with a paths field."""
        target_dir.mkdir()
        run_init(str(target_dir))

        rules_dir = target_dir / ".claude" / "rules"
        for filename in RULES:
            content = (rules_dir / filename).read_text(encoding="utf-8")
            assert content.startswith("---\n")
            assert "paths:" in content

    def test_rules_idempotent(self, target_dir):
        """Running init twice produces the same rule files with no duplication."""
        target_dir.mkdir()
        run_init(str(target_dir))

        rules_dir = target_dir / ".claude" / "rules"
        contents_first = {
            f.name: f.read_text(encoding="utf-8")
            for f in rules_dir.iterdir() if f.is_file()
        }

        run_init(str(target_dir))

        contents_second = {
            f.name: f.read_text(encoding="utf-8")
            for f in rules_dir.iterdir() if f.is_file()
        }
        assert contents_first == contents_second

    def test_rules_preserve_custom_files(self, target_dir):
        """Init does not delete custom rule files added by the developer."""
        target_dir.mkdir()
        rules_dir = target_dir / ".claude" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        custom = rules_dir / "my-custom-rule.md"
        custom.write_text("---\npaths:\n  - lib/**\n---\nMy rule.\n",
                          encoding="utf-8")

        run_init(str(target_dir))

        assert custom.exists()
        assert custom.read_text(encoding="utf-8") == (
            "---\npaths:\n  - lib/**\n---\nMy rule.\n"
        )
        # All CLASI rules also present
        for filename in RULES:
            assert (rules_dir / filename).exists()

    def test_rules_update_changed_content(self, target_dir):
        """Init overwrites a CLASI rule if its content has changed."""
        target_dir.mkdir()
        rules_dir = target_dir / ".claude" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        stale = rules_dir / "clasi-artifacts.md"
        stale.write_text("old content", encoding="utf-8")

        run_init(str(target_dir))

        actual = stale.read_text(encoding="utf-8")
        assert actual == RULES["clasi-artifacts.md"]
