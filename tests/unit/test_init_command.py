"""Tests for clasi.init_command module."""

import json

import pytest

from clasi.init_command import (
    run_init,
    RULES,
    _detect_mcp_command,
    _PLUGIN_DIR,
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
        content = skill.read_text(encoding="utf-8")
        assert "description:" in content
        assert "/se" in content

    def test_creates_all_plugin_skills(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        skills_dir = target_dir / ".claude" / "skills"
        # Check a representative set of skills exist
        for name in ["se", "plan-sprint", "execute-sprint", "todo",
                      "oop", "code-review", "systematic-debugging"]:
            skill = skills_dir / name / "SKILL.md"
            assert skill.exists(), f"Skill {name} not created"

    def test_skills_have_name_in_frontmatter(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        skills_dir = target_dir / ".claude" / "skills"
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            content = skill_md.read_text(encoding="utf-8")
            assert "name:" in content, f"{skill_dir.name} missing name in frontmatter"

    def test_se_skill_idempotent(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))
        first = (target_dir / ".claude" / "skills" / "se" / "SKILL.md").read_text(encoding="utf-8")

        run_init(str(target_dir))
        second = (target_dir / ".claude" / "skills" / "se" / "SKILL.md").read_text(encoding="utf-8")

        assert first == second

    def test_creates_agent_definitions(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        agents_dir = target_dir / ".claude" / "agents"
        for name in ["sprint-planner", "programmer"]:
            agent = agents_dir / name / "agent.md"
            assert agent.exists(), f"Agent {name} not created"

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
        expected = _detect_mcp_command(target_dir)
        assert data["mcpServers"]["clasi"] == expected

    def test_idempotent(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))
        run_init(str(target_dir))

        mcp_json = target_dir / ".mcp.json"
        data = json.loads(mcp_json.read_text(encoding="utf-8"))
        expected = _detect_mcp_command(target_dir)
        assert data["mcpServers"]["clasi"] == expected

    def test_merges_existing_mcp_json(self, target_dir):
        target_dir.mkdir()
        mcp_json = target_dir / ".mcp.json"
        existing = {"mcpServers": {"other": {"command": "other"}}}
        mcp_json.write_text(json.dumps(existing), encoding="utf-8")

        run_init(str(target_dir))

        data = json.loads(mcp_json.read_text(encoding="utf-8"))
        assert data["mcpServers"]["other"] == {"command": "other"}
        expected = _detect_mcp_command(target_dir)
        assert data["mcpServers"]["clasi"] == expected

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

    def test_creates_todo_directories(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        todo_dir = target_dir / "docs" / "clasi" / "todo"
        assert todo_dir.exists()
        assert (todo_dir / "in-progress").exists()
        assert (todo_dir / "done").exists()


class TestHooksConfig:
    def test_init_creates_hooks_in_settings(self, target_dir):
        """Init creates hooks in settings.json from plugin hooks.json."""
        target_dir.mkdir()
        run_init(str(target_dir))

        settings_path = target_dir / ".claude" / "settings.json"
        assert settings_path.exists()
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "hooks" in data
        # Should have PreToolUse hook (role-guard)
        assert "PreToolUse" in data["hooks"]

    def test_hooks_idempotent(self, target_dir):
        """Running init twice does not duplicate hook entries."""
        target_dir.mkdir()
        run_init(str(target_dir))
        run_init(str(target_dir))

        settings_path = target_dir / ".claude" / "settings.json"
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        # Each event type should not have duplicates
        for event_type, entries in data["hooks"].items():
            commands = []
            for entry in entries:
                for hook in entry.get("hooks", []):
                    commands.append(hook.get("command", ""))
            assert len(commands) == len(set(commands)), (
                f"Duplicate hooks in {event_type}"
            )

    def test_hooks_preserve_existing_settings(self, target_dir):
        """Hook installation preserves existing keys in settings.json."""
        target_dir.mkdir()
        settings_path = target_dir / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {"other": "kept"}
        settings_path.write_text(json.dumps(existing), encoding="utf-8")

        run_init(str(target_dir))

        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert data["other"] == "kept"
        assert "hooks" in data

    def test_hooks_correct_format(self, target_dir):
        """Hook entries use matcher+hooks format per Claude Code spec."""
        target_dir.mkdir()
        run_init(str(target_dir))

        settings_path = target_dir / ".claude" / "settings.json"
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        for event_type, entries in data["hooks"].items():
            for entry in entries:
                assert "hooks" in entry
                assert isinstance(entry["hooks"], list)

    def test_hooks_preserve_existing_hooks(self, target_dir):
        """Hook installation preserves other existing hook entries."""
        target_dir.mkdir()
        settings_path = target_dir / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "", "hooks": [{"type": "command", "command": "echo pre"}]}
                ],
            }
        }
        settings_path.write_text(json.dumps(existing), encoding="utf-8")

        run_init(str(target_dir))

        data = json.loads(settings_path.read_text(encoding="utf-8"))
        pre_tool = data["hooks"]["PreToolUse"]
        # Existing entry preserved
        assert {"matcher": "", "hooks": [{"type": "command", "command": "echo pre"}]} in pre_tool
        # CLASI role guard added
        assert any("role_guard" in h.get("command", "")
                    for entry in pre_tool for h in entry.get("hooks", []))


class TestRules:
    def test_init_creates_all_rule_files(self, target_dir):
        """Init creates all CLASI rule files."""
        target_dir.mkdir()
        run_init(str(target_dir))

        rules_dir = target_dir / ".claude" / "rules"
        expected = set(RULES.keys())
        created = {f.name for f in rules_dir.iterdir() if f.is_file()}
        assert expected <= created  # CLASI rules are a subset of created files

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
