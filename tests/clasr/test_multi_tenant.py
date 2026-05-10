"""
tests/clasr/test_multi_tenant.py

Multi-tenant integration tests: two providers install into the same target
directory.  Covers:

  A) Marker-block and manifest coexistence / selective uninstall
  B) JSON-merge install (settings.json deep-merge, conflict warning)
  C) JSON-merge uninstall — per-provider key removal
  D) Non-JSON passthrough collision detection
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from clasr.platforms.claude import ClaudeIntegration

# Use the class API directly; expose install/uninstall on a small namespace so
# the existing test bodies don't need rewriting.
class _ClaudePlatform:
    _inst = ClaudeIntegration()
    install = staticmethod(_inst.install)
    uninstall = staticmethod(_inst.uninstall)

claude_platform = _ClaudePlatform()

from tests.clasr.conftest import make_asr_dir


# ---------------------------------------------------------------------------
# Section A: marker-block and manifest coexistence
# ---------------------------------------------------------------------------


class TestMultiTenantCoexistence:
    """Two providers install into the same target; selective uninstall leaves
    the surviving provider's blocks and files intact."""

    @pytest.fixture
    def workspace(self, tmp_path: Path) -> dict:
        """Build two asr/ source dirs and one shared target."""
        src_a = make_asr_dir(
            tmp_path / "a",
            provider="provider_a",
            skill_names=("skill_a",),
            settings_keys=None,  # no settings.json needed for this section
        )
        src_b = make_asr_dir(
            tmp_path / "b",
            provider="provider_b",
            skill_names=("skill_b",),
            settings_keys=None,
        )
        target = tmp_path / "project"
        target.mkdir()
        return {"src_a": src_a, "src_b": src_b, "target": target}

    def test_both_manifests_exist_after_install(self, workspace: dict) -> None:
        """After installing both providers, each has a manifest file."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        manifest_dir = target / ".claude" / ".clasr-manifest"
        assert (manifest_dir / "provider_a.json").exists(), "provider_a manifest missing"
        assert (manifest_dir / "provider_b.json").exists(), "provider_b manifest missing"

    def test_agents_md_contains_both_blocks(self, workspace: dict) -> None:
        """AGENTS.md contains named marker blocks for both providers."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        text = (target / "AGENTS.md").read_text(encoding="utf-8")
        assert "<!-- BEGIN clasr:provider_a -->" in text, "provider_a block missing from AGENTS.md"
        assert "<!-- BEGIN clasr:provider_b -->" in text, "provider_b block missing from AGENTS.md"

    def test_claude_md_contains_both_blocks(self, workspace: dict) -> None:
        """CLAUDE.md contains named marker blocks for both providers."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        text = (target / "CLAUDE.md").read_text(encoding="utf-8")
        assert "<!-- BEGIN clasr:provider_a -->" in text, "provider_a block missing from CLAUDE.md"
        assert "<!-- BEGIN clasr:provider_b -->" in text, "provider_b block missing from CLAUDE.md"

    def test_both_skills_coexist(self, workspace: dict) -> None:
        """Both providers' skill files exist under .claude/skills/ simultaneously."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        skills_dir = target / ".claude" / "skills"
        assert (skills_dir / "skill_a" / "SKILL.md").exists(), "skill_a missing"
        assert (skills_dir / "skill_b" / "SKILL.md").exists(), "skill_b missing"

    def test_uninstall_a_removes_a_manifest(self, workspace: dict) -> None:
        """Uninstalling provider_a deletes provider_a's manifest."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        claude_platform.uninstall(target=target, provider="provider_a")

        manifest_a = target / ".claude" / ".clasr-manifest" / "provider_a.json"
        assert not manifest_a.exists(), "provider_a manifest should be deleted after uninstall"

    def test_uninstall_a_leaves_b_manifest(self, workspace: dict) -> None:
        """Uninstalling provider_a does NOT delete provider_b's manifest."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        claude_platform.uninstall(target=target, provider="provider_a")

        manifest_b = target / ".claude" / ".clasr-manifest" / "provider_b.json"
        assert manifest_b.exists(), "provider_b manifest was removed when only provider_a was uninstalled"

    def test_uninstall_a_removes_a_skill(self, workspace: dict) -> None:
        """Uninstalling provider_a removes its skill file."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        claude_platform.uninstall(target=target, provider="provider_a")

        skill_a = target / ".claude" / "skills" / "skill_a" / "SKILL.md"
        assert not skill_a.exists(), "skill_a should be removed after provider_a uninstall"

    def test_uninstall_a_leaves_b_skill(self, workspace: dict) -> None:
        """Uninstalling provider_a does NOT remove provider_b's skill."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        claude_platform.uninstall(target=target, provider="provider_a")

        skill_b = target / ".claude" / "skills" / "skill_b" / "SKILL.md"
        assert skill_b.exists(), "skill_b was removed when only provider_a was uninstalled"

    def test_uninstall_a_strips_a_block_from_agents_md(self, workspace: dict) -> None:
        """After uninstalling provider_a, its block is gone from AGENTS.md."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        claude_platform.uninstall(target=target, provider="provider_a")

        text = (target / "AGENTS.md").read_text(encoding="utf-8")
        assert "<!-- BEGIN clasr:provider_a -->" not in text, (
            "provider_a block still present in AGENTS.md after uninstall"
        )

    def test_uninstall_a_leaves_b_block_in_agents_md(self, workspace: dict) -> None:
        """After uninstalling provider_a, provider_b's block is intact in AGENTS.md."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        claude_platform.uninstall(target=target, provider="provider_a")

        text = (target / "AGENTS.md").read_text(encoding="utf-8")
        assert "<!-- BEGIN clasr:provider_b -->" in text, (
            "provider_b block was stripped from AGENTS.md when only provider_a was uninstalled"
        )

    def test_uninstall_a_strips_a_block_from_claude_md(self, workspace: dict) -> None:
        """After uninstalling provider_a, its block is gone from CLAUDE.md."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        claude_platform.uninstall(target=target, provider="provider_a")

        text = (target / "CLAUDE.md").read_text(encoding="utf-8")
        assert "<!-- BEGIN clasr:provider_a -->" not in text, (
            "provider_a block still present in CLAUDE.md after uninstall"
        )

    def test_uninstall_a_leaves_b_block_in_claude_md(self, workspace: dict) -> None:
        """After uninstalling provider_a, provider_b's block is intact in CLAUDE.md."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        claude_platform.uninstall(target=target, provider="provider_a")

        text = (target / "CLAUDE.md").read_text(encoding="utf-8")
        assert "<!-- BEGIN clasr:provider_b -->" in text, (
            "provider_b block was stripped from CLAUDE.md when only provider_a was uninstalled"
        )


# ---------------------------------------------------------------------------
# Section B: JSON-merge install (overlapping top-level keys → conflict warning)
# ---------------------------------------------------------------------------


class TestJsonMergeInstall:
    """Two providers ship settings.json with overlapping top-level keys.
    The second install merges and warns; both services end up in the file."""

    @pytest.fixture
    def workspace(self, tmp_path: Path) -> dict:
        """Both providers ship settings.json with the same top-level key (mcpServers)."""
        src_a = make_asr_dir(
            tmp_path / "a",
            provider="provider_a",
            skill_names=("skill_a",),
            settings_keys={"mcpServers": {"svc_a": {"command": "x"}}},
        )
        src_b = make_asr_dir(
            tmp_path / "b",
            provider="provider_b",
            skill_names=("skill_b",),
            settings_keys={"mcpServers": {"svc_b": {"command": "y"}}},
        )
        target = tmp_path / "project"
        target.mkdir()
        return {"src_a": src_a, "src_b": src_b, "target": target}

    def test_both_services_in_settings_after_install(self, workspace: dict) -> None:
        """After installing both providers, .claude/settings.json contains svc_a and svc_b."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        settings_path = target / ".claude" / "settings.json"
        assert settings_path.exists(), "settings.json missing after install"

        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "svc_a" in data.get("mcpServers", {}), "svc_a missing from merged settings"
        assert "svc_b" in data.get("mcpServers", {}), "svc_b missing from merged settings"

    def test_provider_a_manifest_records_copy(self, workspace: dict) -> None:
        """provider_a is the first writer; its manifest records kind='copy' for settings.json."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        mf = json.loads(
            (target / ".claude" / ".clasr-manifest" / "provider_a.json").read_text(encoding="utf-8")
        )
        settings_entry = next(
            (e for e in mf["entries"] if e["path"] == ".claude/settings.json"),
            None,
        )
        assert settings_entry is not None, "settings.json entry missing from provider_a manifest"
        assert settings_entry["kind"] == "copy", (
            f"Expected kind='copy' for first writer; got '{settings_entry['kind']}'"
        )

    def test_provider_b_manifest_records_json_merged(self, workspace: dict) -> None:
        """provider_b merges into existing file; its manifest records kind='json-merged'."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        mf = json.loads(
            (target / ".claude" / ".clasr-manifest" / "provider_b.json").read_text(encoding="utf-8")
        )
        settings_entry = next(
            (e for e in mf["entries"] if e["path"] == ".claude/settings.json"),
            None,
        )
        assert settings_entry is not None, "settings.json entry missing from provider_b manifest"
        assert settings_entry["kind"] == "json-merged", (
            f"Expected kind='json-merged' for second writer; got '{settings_entry['kind']}'"
        )
        assert "mcpServers" in settings_entry.get("keys", []), (
            "Expected 'mcpServers' in provider_b manifest keys"
        )
        assert isinstance(settings_entry.get("contributed"), dict), (
            "Expected 'contributed' field to be a dict in provider_b manifest"
        )
        assert "mcpServers" in settings_entry["contributed"], (
            "Expected 'mcpServers' key inside provider_b manifest 'contributed' dict"
        )

    def test_conflict_warning_emitted_to_stderr(
        self, workspace: dict, capsys: pytest.CaptureFixture
    ) -> None:
        """Installing provider_b prints a WARNING to stderr for the conflicting 'mcpServers' key."""
        target = workspace["target"]
        claude_platform.install(source=workspace["src_a"], target=target, provider="provider_a")
        claude_platform.install(source=workspace["src_b"], target=target, provider="provider_b")

        captured = capsys.readouterr()
        stderr = captured.err

        assert "WARNING" in stderr, "No WARNING emitted to stderr on JSON-merge conflict"
        assert "mcpServers" in stderr, "Conflicting key 'mcpServers' not named in warning"
        # Both provider names should appear in the warning.
        assert "provider_a" in stderr or "provider_b" in stderr, (
            "Neither provider name appears in the conflict warning"
        )


# ---------------------------------------------------------------------------
# Section C: JSON-merge uninstall — per-provider key removal
# ---------------------------------------------------------------------------


class TestJsonMergeUninstall:
    """JSON-merge uninstall removes the top-level keys contributed by a provider."""

    def test_c1_uninstall_b_leaves_a_key(self, tmp_path: Path) -> None:
        """C1: Non-overlapping keys — uninstalling provider_b removes keyB, leaves keyA."""
        src_a = make_asr_dir(
            tmp_path / "a",
            provider="provider_a",
            skill_names=("skill_a",),
            settings_keys={"keyA": "valA"},
        )
        src_b = make_asr_dir(
            tmp_path / "b",
            provider="provider_b",
            skill_names=("skill_b",),
            settings_keys={"keyB": "valB"},
        )
        target = tmp_path / "project"
        target.mkdir()

        claude_platform.install(source=src_a, target=target, provider="provider_a")
        claude_platform.install(source=src_b, target=target, provider="provider_b")

        # Both keys should be present after both installs.
        settings_path = target / ".claude" / "settings.json"
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "keyA" in data, "keyA missing after both installs"
        assert "keyB" in data, "keyB missing after both installs"

        # Uninstall provider_b.
        claude_platform.uninstall(target=target, provider="provider_b")

        # settings.json should still exist with only keyA.
        assert settings_path.exists(), "settings.json deleted too early (keyA still owned by provider_a)"
        data_after = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "keyA" in data_after, "keyA was removed when only provider_b was uninstalled"
        assert "keyB" not in data_after, "keyB still present after provider_b uninstall"

    def test_c2_file_deleted_when_both_uninstalled(self, tmp_path: Path) -> None:
        """C2: After both providers uninstall, settings.json is deleted (becomes empty)."""
        src_a = make_asr_dir(
            tmp_path / "a",
            provider="provider_a",
            skill_names=("skill_a",),
            settings_keys={"keyA": "valA"},
        )
        src_b = make_asr_dir(
            tmp_path / "b",
            provider="provider_b",
            skill_names=("skill_b",),
            settings_keys={"keyB": "valB"},
        )
        target = tmp_path / "project"
        target.mkdir()

        claude_platform.install(source=src_a, target=target, provider="provider_a")
        claude_platform.install(source=src_b, target=target, provider="provider_b")

        # Uninstall both providers.
        claude_platform.uninstall(target=target, provider="provider_b")
        claude_platform.uninstall(target=target, provider="provider_a")

        settings_path = target / ".claude" / "settings.json"
        assert not settings_path.exists(), (
            "settings.json still exists after both providers uninstalled (should be deleted)"
        )


# ---------------------------------------------------------------------------
# Section C2: JSON-merge uninstall — overlapping key scenario
# ---------------------------------------------------------------------------


class TestJsonMergeUninstallOverlapping:
    """JSON-merge uninstall with overlapping keys between two providers.

    This exercises the original bug: when both providers set the same key,
    selective uninstall of one provider must preserve the surviving provider's
    data rather than removing the shared key entirely.
    """

    def test_c2_1_uninstall_b_leaves_a_model_intact(self, tmp_path: Path) -> None:
        """C2-1: Both providers set `model` to the same value.

        Provider-B's `contributed` diff is empty for `model` (no change from
        provider-A's value), so uninstalling B leaves A's `model` value intact.
        """
        src_a = make_asr_dir(
            tmp_path / "a",
            provider="provider_a",
            skill_names=("skill_a",),
            settings_keys={"model": "claude-3-sonnet"},
        )
        src_b = make_asr_dir(
            tmp_path / "b",
            provider="provider_b",
            skill_names=("skill_b",),
            settings_keys={"model": "claude-3-sonnet"},
        )
        target = tmp_path / "project"
        target.mkdir()

        claude_platform.install(source=src_a, target=target, provider="provider_a")
        claude_platform.install(source=src_b, target=target, provider="provider_b")

        # Uninstall provider_b only.
        claude_platform.uninstall(target=target, provider="provider_b")

        settings_path = target / ".claude" / "settings.json"
        assert settings_path.exists(), (
            "settings.json was deleted prematurely — provider_a still owns 'model'"
        )
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "model" in data, "provider_a's 'model' key was removed when only provider_b was uninstalled"
        assert data["model"] == "claude-3-sonnet", (
            f"provider_a's 'model' value corrupted; expected 'claude-3-sonnet', got '{data['model']}'"
        )

    def test_c2_2_uninstall_b_leaves_a_permissions_intact(self, tmp_path: Path) -> None:
        """C2-2: Both providers set `permissions` with non-overlapping sub-keys.

        Provider-A owns permissions.allow; provider-B adds permissions.deny.
        Uninstalling B removes only the `deny` sub-key and leaves A's `allow` list.
        """
        src_a = make_asr_dir(
            tmp_path / "a",
            provider="provider_a",
            skill_names=("skill_a",),
            settings_keys={"permissions": {"allow": ["read", "write"]}},
        )
        src_b = make_asr_dir(
            tmp_path / "b",
            provider="provider_b",
            skill_names=("skill_b",),
            settings_keys={"permissions": {"deny": ["execute"]}},
        )
        target = tmp_path / "project"
        target.mkdir()

        claude_platform.install(source=src_a, target=target, provider="provider_a")
        claude_platform.install(source=src_b, target=target, provider="provider_b")

        # Both sub-keys should be present after both installs.
        settings_path = target / ".claude" / "settings.json"
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert data.get("permissions", {}).get("allow") == ["read", "write"], (
            "permissions.allow missing after both installs"
        )
        assert data.get("permissions", {}).get("deny") == ["execute"], (
            "permissions.deny missing after both installs"
        )

        # Uninstall provider_b.
        claude_platform.uninstall(target=target, provider="provider_b")

        # settings.json must still exist with provider_a's permissions intact.
        assert settings_path.exists(), (
            "settings.json was deleted — provider_a still owns permissions.allow"
        )
        data_after = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "permissions" in data_after, (
            "provider_a's 'permissions' key was removed when only provider_b was uninstalled"
        )
        assert data_after["permissions"].get("allow") == ["read", "write"], (
            "provider_a's 'permissions.allow' was corrupted after provider_b uninstall"
        )
        assert "deny" not in data_after["permissions"], (
            "provider_b's 'permissions.deny' was not removed on uninstall"
        )

    def test_c2_3_uninstall_both_deletes_file(self, tmp_path: Path) -> None:
        """C2-3: After uninstalling B then A (both with overlapping `model` key), settings.json is deleted."""
        src_a = make_asr_dir(
            tmp_path / "a",
            provider="provider_a",
            skill_names=("skill_a",),
            settings_keys={"model": "claude-3-sonnet"},
        )
        src_b = make_asr_dir(
            tmp_path / "b",
            provider="provider_b",
            skill_names=("skill_b",),
            settings_keys={"model": "claude-3-sonnet"},
        )
        target = tmp_path / "project"
        target.mkdir()

        claude_platform.install(source=src_a, target=target, provider="provider_a")
        claude_platform.install(source=src_b, target=target, provider="provider_b")

        # Uninstall both providers.
        claude_platform.uninstall(target=target, provider="provider_b")
        claude_platform.uninstall(target=target, provider="provider_a")

        settings_path = target / ".claude" / "settings.json"
        assert not settings_path.exists(), (
            "settings.json still exists after both providers uninstalled (should be deleted)"
        )

    def test_c2_4_old_format_manifest_fallback_emits_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """C2-4: Old-format manifest (no 'contributed' field) falls back and emits WARNING.

        Manually craft a manifest entry for provider_b with 'json-merged' kind but
        without the 'contributed' field, then call uninstall() and confirm that:
        - A WARNING is printed to stderr.
        - The uninstall completes without raising an exception.
        """
        import clasr.manifest as mf_module

        # Install provider_a normally.
        src_a = make_asr_dir(
            tmp_path / "a",
            provider="provider_a",
            skill_names=("skill_a",),
            settings_keys={"keyA": "valA", "keyB": "shared"},
        )
        target = tmp_path / "project"
        target.mkdir()
        claude_platform.install(source=src_a, target=target, provider="provider_a")

        # Write provider_b's settings contribution to the target file directly.
        settings_path = target / ".claude" / "settings.json"
        existing = json.loads(settings_path.read_text(encoding="utf-8"))
        existing["keyB"] = "provider_b_value"
        settings_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        # Craft an old-format manifest for provider_b (no 'contributed' field).
        claude_dir = target / ".claude"
        old_format_manifest = {
            "version": 1,
            "provider": "provider_b",
            "platform": "claude",
            "source": str(tmp_path / "b"),
            "entries": [
                {
                    "path": ".claude/settings.json",
                    "kind": "json-merged",
                    "keys": ["keyB"],
                    # Note: deliberately no 'contributed' field — this is the old format.
                }
            ],
        }
        mf_module.write_manifest(claude_dir, "provider_b", old_format_manifest)

        # Uninstall provider_b using the old-format manifest.
        claude_platform.uninstall(target=target, provider="provider_b")

        captured = capsys.readouterr()
        assert "WARNING" in captured.err, (
            "Expected a WARNING on stderr for old-format manifest fallback; got none"
        )

        # Uninstall must complete without error; provider_b manifest is gone.
        manifest_b = target / ".claude" / ".clasr-manifest" / "provider_b.json"
        assert not manifest_b.exists(), (
            "provider_b manifest should be deleted after uninstall"
        )


# ---------------------------------------------------------------------------
# Section D: Non-JSON passthrough collision
# ---------------------------------------------------------------------------


class TestPassthroughCollision:
    """Two providers shipping the same non-JSON passthrough path — second install raises."""

    def test_collision_raises_runtime_error(self, tmp_path: Path) -> None:
        """Installing provider_b when provider_a owns the same file raises RuntimeError."""
        src_a = make_asr_dir(
            tmp_path / "a",
            provider="provider_a",
            skill_names=(),
            settings_keys=None,
            extra_passthrough={"claude/commands/foo.md": "from a"},
        )
        src_b = make_asr_dir(
            tmp_path / "b",
            provider="provider_b",
            skill_names=(),
            settings_keys=None,
            extra_passthrough={"claude/commands/foo.md": "from b"},
        )
        target = tmp_path / "project"
        target.mkdir()

        claude_platform.install(source=src_a, target=target, provider="provider_a")

        with pytest.raises(RuntimeError) as exc_info:
            claude_platform.install(source=src_b, target=target, provider="provider_b")

        error_msg = str(exc_info.value)
        # The error should mention the conflict — at least one of the provider names.
        assert "provider_a" in error_msg or "provider_b" in error_msg, (
            f"Error message does not name a provider: {error_msg}"
        )

    def test_collision_does_not_overwrite_file(self, tmp_path: Path) -> None:
        """When provider_b install raises, provider_a's file content is preserved."""
        src_a = make_asr_dir(
            tmp_path / "a",
            provider="provider_a",
            skill_names=(),
            settings_keys=None,
            extra_passthrough={"claude/commands/foo.md": "from a"},
        )
        src_b = make_asr_dir(
            tmp_path / "b",
            provider="provider_b",
            skill_names=(),
            settings_keys=None,
            extra_passthrough={"claude/commands/foo.md": "from b"},
        )
        target = tmp_path / "project"
        target.mkdir()

        claude_platform.install(source=src_a, target=target, provider="provider_a")

        with pytest.raises(RuntimeError):
            claude_platform.install(source=src_b, target=target, provider="provider_b")

        foo_md = target / ".claude" / "commands" / "foo.md"
        assert foo_md.exists(), ".claude/commands/foo.md was removed during failed install"
        assert foo_md.read_text(encoding="utf-8") == "from a", (
            "foo.md content was overwritten during failed provider_b install"
        )
