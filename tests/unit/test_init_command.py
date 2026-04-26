"""Tests for clasi.init_command module."""

import json

import pytest

from clasi.init_command import (
    run_init,
    RULES,
    _detect_mcp_command,
    _PLUGIN_DIR,
)
from clasi.platforms.claude import install as claude_install, uninstall as claude_uninstall


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

    def test_creates_log_directory_with_gitignore(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))

        log_dir = target_dir / "docs" / "clasi" / "log"
        assert log_dir.exists()

        gitignore = log_dir / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text(encoding="utf-8")
        assert "*" in content
        assert "!.gitignore" in content

    def test_log_gitignore_idempotent(self, target_dir):
        target_dir.mkdir()
        run_init(str(target_dir))
        run_init(str(target_dir))

        gitignore = target_dir / "docs" / "clasi" / "log" / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text(encoding="utf-8")
        assert "*" in content

    def test_detect_mcp_command_no_pyproject(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "target"
        target.mkdir()
        cmd = _detect_mcp_command(target)
        assert cmd == {"command": "clasi", "args": ["mcp"]}

    def test_detect_mcp_command_always_uses_clasi(
        self, tmp_path, monkeypatch
    ):
        """`clasi mcp` is the canonical invocation regardless of pyproject.toml
        contents. The previous `uv run` heuristic was dev-only and broke for
        end-user installs without uv. Projects that want `uv run` can edit
        their MCP config by hand.
        """
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "target"
        target.mkdir()
        (target / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1"\n', encoding="utf-8"
        )
        cmd = _detect_mcp_command(target)
        assert cmd == {"command": "clasi", "args": ["mcp"]}

    def test_source_code_rule_no_pytest(self):
        assert "uv run pytest" not in RULES["source-code.md"]

    def test_git_commits_rule_no_pytest(self):
        assert "uv run pytest" not in RULES["git-commits.md"]


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

    def test_hooks_overwrite_old_commands(self, target_dir):
        """Hook installation overwrites old hook commands (e.g. python3) with new clasi commands."""
        target_dir.mkdir()
        settings_path = target_dir / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        old_hooks = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Edit|Write|MultiEdit",
                        "hooks": [{"type": "command", "command": "python3 role_guard.py"}],
                    }
                ]
            }
        }
        settings_path.write_text(json.dumps(old_hooks), encoding="utf-8")

        run_init(str(target_dir))

        data = json.loads(settings_path.read_text(encoding="utf-8"))
        pre_tool = data["hooks"]["PreToolUse"]
        # Old python3 command must be gone
        all_commands = [
            h.get("command", "")
            for entry in pre_tool
            for h in entry.get("hooks", [])
        ]
        assert not any("python3" in cmd for cmd in all_commands)
        # New clasi hook role-guard command is present
        assert any("clasi hook role-guard" in cmd for cmd in all_commands)

    def test_hooks_unchanged_when_already_correct(self, target_dir):
        """Running init on a directory that already has correct hooks does not change settings.json."""
        target_dir.mkdir()
        # Pre-install the correct hooks
        run_init(str(target_dir))
        settings_path = target_dir / ".claude" / "settings.json"
        data_before = json.loads(settings_path.read_text(encoding="utf-8"))

        # Run again — hooks section should be identical (no mutation)
        run_init(str(target_dir))
        data_after = json.loads(settings_path.read_text(encoding="utf-8"))
        assert data_before["hooks"] == data_after["hooks"]

    def test_hooks_preserve_permissions_key(self, target_dir):
        """A pre-existing 'permissions' key in settings.json is preserved after run_init."""
        target_dir.mkdir()
        settings_path = target_dir / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {"permissions": {"allow": ["Bash(*)"]}, "other": "kept"}
        settings_path.write_text(json.dumps(existing), encoding="utf-8")

        run_init(str(target_dir))

        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert data["permissions"] == {"allow": ["Bash(*)"]}
        assert data["other"] == "kept"
        assert "hooks" in data

    def test_no_py_files_copied_to_hooks_dir(self, target_dir):
        """No .py files are copied to <target>/.claude/hooks/ during init."""
        target_dir.mkdir()
        run_init(str(target_dir))

        hooks_dir = target_dir / ".claude" / "hooks"
        if hooks_dir.exists():
            py_files = list(hooks_dir.glob("*.py"))
            assert py_files == [], f"Unexpected .py files: {py_files}"


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


class TestPlatformsClaude:
    """Integration tests for clasi.platforms.claude install/uninstall."""

    def test_install_produces_same_file_set_as_run_init(self, tmp_path):
        """claude.install() produces the same Claude-specific artifacts as run_init().

        run_init() also creates .mcp.json and docs/ directories (shared setup).
        This test verifies only the Claude-owned subset of files is created by install().
        """
        target = tmp_path / "repo"
        target.mkdir()
        mcp_config = _detect_mcp_command(target)
        claude_install(target, mcp_config)

        # Skills, agents, rules — same as run_init
        assert (target / ".claude" / "skills" / "se" / "SKILL.md").exists()
        assert (target / ".claude" / "agents" / "programmer" / "agent.md").exists()
        for filename in RULES:
            assert (target / ".claude" / "rules" / filename).exists()

        # settings.local.json permission
        data = json.loads(
            (target / ".claude" / "settings.local.json").read_text(encoding="utf-8")
        )
        assert "mcp__clasi__*" in data["permissions"]["allow"]

        # CLAUDE.md written
        assert (target / "CLAUDE.md").exists()
        assert "CLASI Software Engineering Process" in (
            target / "CLAUDE.md"
        ).read_text(encoding="utf-8")

    def test_run_init_delegates_to_claude_install(self, tmp_path):
        """run_init() and standalone claude_install() produce the same Claude artifacts.

        Compare the two approaches on fresh directories: all Claude-managed
        files must be byte-identical.
        """
        target_a = tmp_path / "a"
        target_a.mkdir()
        run_init(str(target_a))

        target_b = tmp_path / "b"
        target_b.mkdir()
        mcp_config = _detect_mcp_command(target_b)
        claude_install(target_b, mcp_config)

        # Compare rule files
        for filename in RULES:
            content_a = (target_a / ".claude" / "rules" / filename).read_text(encoding="utf-8")
            content_b = (target_b / ".claude" / "rules" / filename).read_text(encoding="utf-8")
            assert content_a == content_b, f"Rule {filename} differs"

        # Compare settings.local.json
        data_a = json.loads(
            (target_a / ".claude" / "settings.local.json").read_text(encoding="utf-8")
        )
        data_b = json.loads(
            (target_b / ".claude" / "settings.local.json").read_text(encoding="utf-8")
        )
        assert data_a["permissions"]["allow"] == data_b["permissions"]["allow"]

    def test_uninstall_removes_clasi_section_from_claude_md(self, tmp_path):
        """uninstall() strips the CLASI:START/END block from CLAUDE.md.

        When CLAUDE.md held only the CLASI block, the file is removed
        entirely (matches the AGENTS.md behavior in the Codex installer).
        """
        target = tmp_path / "repo"
        target.mkdir()
        mcp_config = _detect_mcp_command(target)
        claude_install(target, mcp_config)

        claude_md = target / "CLAUDE.md"
        assert "<!-- CLASI:START -->" in claude_md.read_text(encoding="utf-8")

        claude_uninstall(target)

        # File should be gone (CLASI was its only content), or if it still
        # exists it must contain no CLASI markers.
        if claude_md.exists():
            content = claude_md.read_text(encoding="utf-8")
            assert "<!-- CLASI:START -->" not in content
            assert "<!-- CLASI:END -->" not in content

    def test_uninstall_preserves_user_content_in_claude_md(self, tmp_path):
        """User content outside the CLASI block survives uninstall."""
        target = tmp_path / "repo"
        target.mkdir()
        mcp_config = _detect_mcp_command(target)
        claude_install(target, mcp_config)

        claude_md = target / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(
            "# My Project\n\nHand-written notes.\n\n" + existing,
            encoding="utf-8",
        )

        claude_uninstall(target)

        assert claude_md.exists()
        content = claude_md.read_text(encoding="utf-8")
        assert "# My Project" in content
        assert "Hand-written notes." in content
        assert "<!-- CLASI:START -->" not in content

    def test_uninstall_removes_rule_files(self, tmp_path):
        """uninstall() deletes CLASI-managed rule files."""
        target = tmp_path / "repo"
        target.mkdir()
        mcp_config = _detect_mcp_command(target)
        claude_install(target, mcp_config)
        claude_uninstall(target)

        rules_dir = target / ".claude" / "rules"
        for filename in RULES:
            assert not (rules_dir / filename).exists(), f"Rule {filename} not removed"

    def test_uninstall_preserves_custom_rule_files(self, tmp_path):
        """uninstall() does not delete user-added rule files."""
        target = tmp_path / "repo"
        target.mkdir()
        mcp_config = _detect_mcp_command(target)
        claude_install(target, mcp_config)

        custom = target / ".claude" / "rules" / "my-team-rule.md"
        custom.write_text("---\npaths:\n  - \"**\"\n---\nCustom rule.\n", encoding="utf-8")

        claude_uninstall(target)

        assert custom.exists(), "Custom rule was incorrectly removed"

    def test_uninstall_removes_mcp_permission(self, tmp_path):
        """uninstall() removes mcp__clasi__* from settings.local.json."""
        target = tmp_path / "repo"
        target.mkdir()
        mcp_config = _detect_mcp_command(target)
        claude_install(target, mcp_config)
        claude_uninstall(target)

        settings_local = target / ".claude" / "settings.local.json"
        if settings_local.exists():
            data = json.loads(settings_local.read_text(encoding="utf-8"))
            allow = data.get("permissions", {}).get("allow", [])
            assert "mcp__clasi__*" not in allow

    def test_uninstall_idempotent(self, tmp_path):
        """Running uninstall twice does not raise errors."""
        target = tmp_path / "repo"
        target.mkdir()
        mcp_config = _detect_mcp_command(target)
        claude_install(target, mcp_config)
        claude_uninstall(target)
        # Second call should not raise
        claude_uninstall(target)
