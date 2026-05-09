"""
tests/unit/test_platform_claude.py

Unit tests for the refactored claude.py skills install:
- Canonical write at .agents/skills/<n>/SKILL.md
- Symlink alias at .claude/skills/<n>/SKILL.md (default mode)
- Copy alias at .claude/skills/<n>/SKILL.md (copy=True)
- Uninstall precision: alias removed, canonical preserved
- Migrate happy path: existing direct-copy → symlink
- Migrate conflict: existing file with different content is left intact
- CLAUDE.md symlink to AGENTS.md (ticket 013-004)
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from clasi.platforms import claude as claude_mod
from clasi.platforms.claude import _PLUGIN_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_skill_name() -> str:
    """Return the first bundled skill name (alphabetically)."""
    plugin_skills = _PLUGIN_DIR / "skills"
    for skill_dir in sorted(plugin_skills.iterdir()):
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            return skill_dir.name
    pytest.skip("No bundled skills found in plugin/skills/")


def _all_skill_names() -> list[str]:
    """Return all bundled skill names."""
    plugin_skills = _PLUGIN_DIR / "skills"
    names = []
    for skill_dir in sorted(plugin_skills.iterdir()):
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            names.append(skill_dir.name)
    return names


# ---------------------------------------------------------------------------
# Canonical write
# ---------------------------------------------------------------------------


class TestCanonicalWrite:
    def test_canonical_exists_after_install(self, tmp_path: Path) -> None:
        """install() writes .agents/skills/<n>/SKILL.md for every bundled skill."""
        claude_mod.install(tmp_path, mcp_config={})

        for name in _all_skill_names():
            canonical = tmp_path / ".agents" / "skills" / name / "SKILL.md"
            assert canonical.exists(), f"Canonical missing for skill: {name}"

    def test_canonical_content_matches_plugin(self, tmp_path: Path) -> None:
        """Canonical content is byte-identical to the bundled plugin source."""
        name = _first_skill_name()
        plugin_src = _PLUGIN_DIR / "skills" / name / "SKILL.md"

        claude_mod.install(tmp_path, mcp_config={})

        canonical = tmp_path / ".agents" / "skills" / name / "SKILL.md"
        assert canonical.read_bytes() == plugin_src.read_bytes()

    def test_canonical_written_without_codex_flag(self, tmp_path: Path) -> None:
        """Canonical is written even when --codex is not active (claude-only install)."""
        # install() is the claude-only install path; codex is separate
        claude_mod.install(tmp_path, mcp_config={})

        for name in _all_skill_names():
            canonical = tmp_path / ".agents" / "skills" / name / "SKILL.md"
            assert canonical.exists(), (
                f".agents/skills/{name}/SKILL.md must exist for claude-only install"
            )

    def test_canonical_is_regular_file(self, tmp_path: Path) -> None:
        """Canonical is a regular file, not a symlink."""
        name = _first_skill_name()
        claude_mod.install(tmp_path, mcp_config={})

        canonical = tmp_path / ".agents" / "skills" / name / "SKILL.md"
        assert canonical.is_file()
        assert not canonical.is_symlink()


# ---------------------------------------------------------------------------
# Symlink alias (default mode)
# ---------------------------------------------------------------------------


class TestSymlinkAlias:
    def test_alias_is_symlink_by_default(self, tmp_path: Path) -> None:
        """Default install creates .claude/skills/<n>/SKILL.md as a symlink."""
        claude_mod.install(tmp_path, mcp_config={})

        name = _first_skill_name()
        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        assert alias.is_symlink(), f".claude/skills/{name}/SKILL.md must be a symlink"

    def test_alias_points_to_canonical(self, tmp_path: Path) -> None:
        """Symlink alias resolves to the canonical path."""
        name = _first_skill_name()
        claude_mod.install(tmp_path, mcp_config={})

        canonical = tmp_path / ".agents" / "skills" / name / "SKILL.md"
        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        assert alias.resolve() == canonical.resolve()

    def test_all_skills_have_symlink_alias(self, tmp_path: Path) -> None:
        """All bundled skills have a symlink alias in .claude/skills/."""
        claude_mod.install(tmp_path, mcp_config={})

        for name in _all_skill_names():
            alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
            assert alias.is_symlink(), f".claude/skills/{name}/SKILL.md must be a symlink"

    def test_alias_readable_content_matches_canonical(self, tmp_path: Path) -> None:
        """Reading through the symlink alias yields the canonical content."""
        name = _first_skill_name()
        claude_mod.install(tmp_path, mcp_config={})

        canonical = tmp_path / ".agents" / "skills" / name / "SKILL.md"
        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        assert alias.read_bytes() == canonical.read_bytes()


# ---------------------------------------------------------------------------
# Copy alias (copy=True)
# ---------------------------------------------------------------------------


class TestCopyAlias:
    def test_alias_is_regular_file_when_copy_true(self, tmp_path: Path) -> None:
        """install(copy=True) creates .claude/skills/<n>/SKILL.md as a regular file."""
        claude_mod.install(tmp_path, mcp_config={}, copy=True)

        name = _first_skill_name()
        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        assert alias.exists()
        assert not alias.is_symlink()

    def test_copy_alias_content_matches_canonical(self, tmp_path: Path) -> None:
        """Copy alias has the same content as the canonical."""
        name = _first_skill_name()
        claude_mod.install(tmp_path, mcp_config={}, copy=True)

        canonical = tmp_path / ".agents" / "skills" / name / "SKILL.md"
        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        assert alias.read_bytes() == canonical.read_bytes()

    def test_canonical_still_exists_when_copy_true(self, tmp_path: Path) -> None:
        """Canonical is still written even in copy mode."""
        claude_mod.install(tmp_path, mcp_config={}, copy=True)

        for name in _all_skill_names():
            canonical = tmp_path / ".agents" / "skills" / name / "SKILL.md"
            assert canonical.exists()
            assert not canonical.is_symlink()


# ---------------------------------------------------------------------------
# Uninstall precision
# ---------------------------------------------------------------------------


class TestUninstallPrecision:
    def test_uninstall_removes_alias(self, tmp_path: Path) -> None:
        """uninstall() removes .claude/skills/<n>/SKILL.md (the alias)."""
        claude_mod.install(tmp_path, mcp_config={})
        claude_mod.uninstall(tmp_path)

        name = _first_skill_name()
        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        assert not alias.exists(), "Alias must be removed by uninstall"

    def test_uninstall_preserves_canonical(self, tmp_path: Path) -> None:
        """uninstall() leaves .agents/skills/<n>/SKILL.md intact."""
        claude_mod.install(tmp_path, mcp_config={})
        claude_mod.uninstall(tmp_path)

        for name in _all_skill_names():
            canonical = tmp_path / ".agents" / "skills" / name / "SKILL.md"
            assert canonical.exists(), (
                f"Canonical .agents/skills/{name}/SKILL.md must survive uninstall"
            )

    def test_uninstall_all_aliases_removed(self, tmp_path: Path) -> None:
        """All skill aliases are removed on uninstall."""
        claude_mod.install(tmp_path, mcp_config={})
        claude_mod.uninstall(tmp_path)

        for name in _all_skill_names():
            alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
            assert not alias.exists(), f"Alias still present: .claude/skills/{name}/SKILL.md"

    def test_uninstall_copy_alias_removed(self, tmp_path: Path) -> None:
        """uninstall() removes a copy-mode alias and preserves the canonical."""
        claude_mod.install(tmp_path, mcp_config={}, copy=True)
        claude_mod.uninstall(tmp_path)

        name = _first_skill_name()
        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        canonical = tmp_path / ".agents" / "skills" / name / "SKILL.md"
        assert not alias.exists(), "Copy alias must be removed by uninstall"
        assert canonical.exists(), "Canonical must survive uninstall"

    def test_uninstall_preserves_user_file_inside_skill_dir(self, tmp_path: Path) -> None:
        """User-added notes.md in .claude/skills/<n>/ survives uninstall."""
        claude_mod.install(tmp_path, mcp_config={})

        name = _first_skill_name()
        user_file = tmp_path / ".claude" / "skills" / name / "notes.md"
        user_file.write_text("my notes", encoding="utf-8")

        claude_mod.uninstall(tmp_path)

        assert user_file.exists(), "User notes.md must survive uninstall"
        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        assert not alias.exists(), "SKILL.md alias must be removed by uninstall"


# ---------------------------------------------------------------------------
# Migrate happy path
# ---------------------------------------------------------------------------


class TestMigrateHappyPath:
    def test_migrate_converts_direct_copy_to_symlink(self, tmp_path: Path) -> None:
        """install(migrate=True) converts a legacy direct-copy alias to a symlink."""
        name = _first_skill_name()
        plugin_src = _PLUGIN_DIR / "skills" / name / "SKILL.md"

        # Set up a legacy direct-copy alias (pre-013 state)
        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.write_bytes(plugin_src.read_bytes())  # same content as canonical

        # Run migrate
        claude_mod.install(tmp_path, mcp_config={}, migrate=True)

        assert alias.is_symlink(), "After migrate, alias must be a symlink"
        canonical = tmp_path / ".agents" / "skills" / name / "SKILL.md"
        assert alias.resolve() == canonical.resolve()

    def test_migrate_is_noop_when_already_symlink(self, tmp_path: Path) -> None:
        """install(migrate=True) is a no-op when alias is already a symlink."""
        # First install (creates symlink)
        claude_mod.install(tmp_path, mcp_config={})

        name = _first_skill_name()
        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        assert alias.is_symlink()  # confirm starting state

        # Re-run with migrate — should remain a symlink, no error
        claude_mod.install(tmp_path, mcp_config={}, migrate=True)

        assert alias.is_symlink()
        canonical = tmp_path / ".agents" / "skills" / name / "SKILL.md"
        assert alias.resolve() == canonical.resolve()


# ---------------------------------------------------------------------------
# Migrate conflict
# ---------------------------------------------------------------------------


class TestMigrateConflict:
    def test_migrate_conflict_leaves_alias_unchanged(self, tmp_path: Path) -> None:
        """install(migrate=True) does not overwrite a conflicting alias."""
        name = _first_skill_name()

        # Set up a legacy alias with different content (conflict scenario)
        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.write_text("# Custom content different from canonical\n", encoding="utf-8")
        original_content = alias.read_bytes()

        # Run migrate — should detect conflict and leave alias unchanged
        claude_mod.install(tmp_path, mcp_config={}, migrate=True)

        # Alias must still be a regular file with the original content
        assert not alias.is_symlink(), "Conflict: alias must not be converted to symlink"
        assert alias.read_bytes() == original_content, "Conflict: alias content must be unchanged"

    def test_migrate_conflict_canonical_still_written(self, tmp_path: Path) -> None:
        """Even on conflict, the canonical is written (install continues)."""
        name = _first_skill_name()

        # Set up a conflicting alias
        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.write_text("# Conflicting content\n", encoding="utf-8")

        claude_mod.install(tmp_path, mcp_config={}, migrate=True)

        canonical = tmp_path / ".agents" / "skills" / name / "SKILL.md"
        assert canonical.exists(), "Canonical must be written even when conflict is detected"


# ---------------------------------------------------------------------------
# Migrate — not-found case
# ---------------------------------------------------------------------------


class TestMigrateNotFound:
    def test_migrate_not_found_skipped_silently(self, tmp_path: Path) -> None:
        """install(migrate=True) with no pre-existing alias is a silent skip."""
        name = _first_skill_name()
        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        assert not alias.exists()  # confirm no pre-existing alias

        # Should not raise; alias is created fresh by the install step.
        claude_mod.install(tmp_path, mcp_config={}, migrate=True)

        # After install the alias exists as a symlink (install creates it).
        assert alias.is_symlink(), "Fresh install must create symlink alias"

    def test_migrate_not_found_does_not_print_error(
        self, tmp_path: Path, capsys
    ) -> None:
        """install(migrate=True) with no pre-existing alias prints no conflict/error."""
        claude_mod.install(tmp_path, mcp_config={}, migrate=True)
        captured = capsys.readouterr()
        assert "Conflict" not in captured.out
        assert "Error" not in captured.out


# ---------------------------------------------------------------------------
# Migrate — summary line
# ---------------------------------------------------------------------------


class TestMigrateSummary:
    def test_summary_line_printed(self, tmp_path: Path, capsys) -> None:
        """install(migrate=True) prints the summary line."""
        claude_mod.install(tmp_path, mcp_config={}, migrate=True)
        captured = capsys.readouterr()
        assert "Migration complete:" in captured.out

    def test_summary_zero_converted_on_fresh_install(
        self, tmp_path: Path, capsys
    ) -> None:
        """Fresh install: summary shows 0 converted (all not-found → skipped)."""
        claude_mod.install(tmp_path, mcp_config={}, migrate=True)
        captured = capsys.readouterr()
        assert "0 converted" in captured.out

    def test_summary_counts_one_migrated(self, tmp_path: Path, capsys) -> None:
        """Summary shows 1 converted when one legacy direct-copy alias is present."""
        name = _first_skill_name()
        plugin_src = _PLUGIN_DIR / "skills" / name / "SKILL.md"

        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.write_bytes(plugin_src.read_bytes())  # matching content

        claude_mod.install(tmp_path, mcp_config={}, migrate=True)
        captured = capsys.readouterr()
        # At least 1 converted (the skill we seeded)
        assert "1 converted" in captured.out or "converted" in captured.out
        # Extract the count and verify >= 1
        import re
        match = re.search(r"(\d+) converted", captured.out)
        assert match and int(match.group(1)) >= 1

    def test_summary_counts_one_conflict(self, tmp_path: Path, capsys) -> None:
        """Summary shows 1 conflict when one alias has mismatched content."""
        name = _first_skill_name()

        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.write_text("# Conflicting content\n", encoding="utf-8")

        claude_mod.install(tmp_path, mcp_config={}, migrate=True)
        captured = capsys.readouterr()
        import re
        match = re.search(r"(\d+) conflicts", captured.out)
        assert match and int(match.group(1)) >= 1


# ---------------------------------------------------------------------------
# Migrate — CLAUDE.md via migrate=True
# ---------------------------------------------------------------------------


class TestMigrateClaudeMd:
    """The CLAUDE.md symlink-migration path was retired. CLAUDE.md is now
    a regular file managed by the marker-block writer, so install(migrate=True)
    has no special behavior for it — the block is written/replaced/appended
    the same way the non-migrate path does. The remaining test confirms
    that legacy callers passing migrate=True still get a sensible install."""

    def test_migrate_flag_still_installs_block(self, tmp_path: Path) -> None:
        """install(migrate=True) still produces a valid CLAUDE.md with the CLASI block."""
        # Pre-existing legacy direct-copy CLAUDE.md (e.g. content matched
        # AGENTS.md from an old install). New installer just appends/replaces
        # the block via marker-block semantics.
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "# CLASI Software Engineering Process\n\n"
            "Old content from a pre-marker-block install.\n",
            encoding="utf-8",
        )

        claude_mod.install(tmp_path, mcp_config={}, migrate=True)

        new_content = claude_md.read_text(encoding="utf-8")
        assert "CLASI:START" in new_content
        assert "CLASI:END" in new_content
        # File is still a regular file (no symlink retroactively created).
        assert not claude_md.is_symlink()


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_install_twice_is_idempotent(self, tmp_path: Path) -> None:
        """Running install twice does not raise errors and leaves alias as symlink."""
        claude_mod.install(tmp_path, mcp_config={})
        claude_mod.install(tmp_path, mcp_config={})

        for name in _all_skill_names():
            alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
            canonical = tmp_path / ".agents" / "skills" / name / "SKILL.md"
            assert alias.is_symlink()
            assert alias.resolve() == canonical.resolve()

    def test_install_twice_copy_mode_idempotent(self, tmp_path: Path) -> None:
        """Running install(copy=True) twice does not raise errors."""
        claude_mod.install(tmp_path, mcp_config={}, copy=True)
        claude_mod.install(tmp_path, mcp_config={}, copy=True)

        name = _first_skill_name()
        alias = tmp_path / ".claude" / "skills" / name / "SKILL.md"
        assert alias.exists()
        assert not alias.is_symlink()


# ---------------------------------------------------------------------------
# CLAUDE.md → AGENTS.md symlink (ticket 013-004)
# ---------------------------------------------------------------------------


class TestClaudeMdSymlink:
    """CLAUDE.md and AGENTS.md are both regular files, each holding the
    CLASI marker block. The previous symlink model was retired so CLASI
    can coexist with other tools (e.g. rundbat) that write their own
    named blocks into CLAUDE.md."""

    def test_agents_md_created_by_install(self, tmp_path: Path) -> None:
        """install() writes AGENTS.md with the CLASI marker block."""
        claude_mod.install(tmp_path, mcp_config={})
        agents_md = tmp_path / "AGENTS.md"
        assert agents_md.exists(), "AGENTS.md must be created by install"
        assert "CLASI:START" in agents_md.read_text(encoding="utf-8")

    def test_claude_md_is_regular_file_with_block(self, tmp_path: Path) -> None:
        """Default install: CLAUDE.md is a regular file containing the CLASI block."""
        claude_mod.install(tmp_path, mcp_config={})
        claude_md = tmp_path / "CLAUDE.md"
        assert claude_md.exists()
        assert not claude_md.is_symlink(), "CLAUDE.md is no longer a symlink"
        assert "CLASI:START" in claude_md.read_text(encoding="utf-8")

    def test_both_files_exist_claude_only_install(self, tmp_path: Path) -> None:
        """clasi init --claude (no codex): both AGENTS.md and CLAUDE.md exist."""
        claude_mod.install(tmp_path, mcp_config={})
        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / "CLAUDE.md").exists()

    def test_existing_claude_md_with_other_content_preserved(
        self, tmp_path: Path
    ) -> None:
        """If CLAUDE.md already exists with non-CLASI content, install adds
        the CLASI block via marker-block append; the existing content stays."""
        claude_md = tmp_path / "CLAUDE.md"
        original = (
            "<!-- RUNDBAT:START -->\n"
            "# rundbat\n"
            "rundbat-specific content here.\n"
            "<!-- RUNDBAT:END -->\n"
        )
        claude_md.write_text(original, encoding="utf-8")

        claude_mod.install(tmp_path, mcp_config={})

        new_content = claude_md.read_text(encoding="utf-8")
        # Existing block survives.
        assert "RUNDBAT:START" in new_content
        assert "rundbat-specific content here." in new_content
        # CLASI block was appended.
        assert "CLASI:START" in new_content
        assert "CLASI:END" in new_content

    def test_install_twice_idempotent(self, tmp_path: Path) -> None:
        """Running install twice leaves CLAUDE.md and AGENTS.md unchanged
        on the second pass (the marker block is replaced in place, not duplicated)."""
        claude_mod.install(tmp_path, mcp_config={})
        first = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")

        claude_mod.install(tmp_path, mcp_config={})
        second = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")

        assert first == second
        # Block appears exactly once.
        assert second.count("CLASI:START") == 1
        assert second.count("CLASI:END") == 1


class TestClaudeMdUninstall:
    """Uninstall behavior for CLAUDE.md alias and AGENTS.md canonical."""

    def test_uninstall_removes_claude_md(self, tmp_path: Path) -> None:
        """uninstall() removes the CLAUDE.md symlink."""
        claude_mod.install(tmp_path, mcp_config={})
        claude_mod.uninstall(tmp_path)
        assert not (tmp_path / "CLAUDE.md").exists(), "CLAUDE.md must be removed"

    def test_uninstall_strips_agents_md_when_codex_absent(self, tmp_path: Path) -> None:
        """uninstall() strips the CLASI block from AGENTS.md when Codex is not installed."""
        claude_mod.install(tmp_path, mcp_config={})
        # No .codex/ directory — Claude-only install
        claude_mod.uninstall(tmp_path)

        agents_md = tmp_path / "AGENTS.md"
        # AGENTS.md should be gone (it contained only the CLASI block)
        # OR its CLASI block should be stripped if user content was present.
        if agents_md.exists():
            assert "CLASI:START" not in agents_md.read_text(encoding="utf-8"), (
                "CLASI block must be removed from AGENTS.md when Codex is absent"
            )

    def test_uninstall_preserves_agents_md_block_when_codex_installed(
        self, tmp_path: Path
    ) -> None:
        """uninstall() leaves AGENTS.md block intact when Codex is also installed."""
        claude_mod.install(tmp_path, mcp_config={})

        # Simulate Codex being installed by creating .codex/
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()

        claude_mod.uninstall(tmp_path)

        agents_md = tmp_path / "AGENTS.md"
        assert agents_md.exists(), "AGENTS.md must survive uninstall when Codex is present"
        assert "CLASI:START" in agents_md.read_text(encoding="utf-8"), (
            "CLASI block in AGENTS.md must be preserved when Codex is present"
        )

    def test_uninstall_removes_copy_mode_claude_md(self, tmp_path: Path) -> None:
        """uninstall() removes a copy-mode CLAUDE.md regular file."""
        claude_mod.install(tmp_path, mcp_config={}, copy=True)
        claude_md = tmp_path / "CLAUDE.md"
        assert claude_md.exists() and not claude_md.is_symlink()

        claude_mod.uninstall(tmp_path)
        assert not claude_md.exists(), "Copy-mode CLAUDE.md must be removed by uninstall"


# ---------------------------------------------------------------------------
# Version stamp — consolidated .clasi/clasi-version
# ---------------------------------------------------------------------------


class TestClaudeVersionStamp:
    def test_install_writes_clasi_clasi_version(self, tmp_path: Path) -> None:
        """install() writes exactly .clasi/clasi-version; no per-platform stamp files."""
        claude_mod.install(tmp_path, mcp_config={})

        stamp = tmp_path / ".clasi" / "clasi-version"
        assert stamp.exists(), ".clasi/clasi-version must exist after install"

        # No old-style per-platform stamp files
        for stale_dir in [".claude", ".agents"]:
            stale = tmp_path / stale_dir / ".clasi-version"
            assert not stale.exists(), (
                f"{stale_dir}/.clasi-version must not be written (old format)"
            )

    def test_install_stamp_is_readable_version(self, tmp_path: Path) -> None:
        """The stamp file contains a non-empty version string."""
        claude_mod.install(tmp_path, mcp_config={})
        content = (tmp_path / ".clasi" / "clasi-version").read_text(encoding="utf-8")
        assert content.strip(), "clasi-version stamp must not be empty"

    def test_install_removes_stale_per_platform_stamps(self, tmp_path: Path) -> None:
        """install() removes pre-existing stale per-platform stamp files."""
        for stale_dir in [".claude", ".agents"]:
            stale = tmp_path / stale_dir / ".clasi-version"
            stale.parent.mkdir(parents=True, exist_ok=True)
            stale.write_text("0.old\n", encoding="utf-8")

        claude_mod.install(tmp_path, mcp_config={})

        for stale_dir in [".claude", ".agents"]:
            stale = tmp_path / stale_dir / ".clasi-version"
            assert not stale.exists(), f"Stale {stale_dir}/.clasi-version must be removed"

    def test_uninstall_removes_clasi_version_stamp(self, tmp_path: Path) -> None:
        """uninstall() removes .clasi/clasi-version."""
        claude_mod.install(tmp_path, mcp_config={})
        claude_mod.uninstall(tmp_path)
        assert not (tmp_path / ".clasi" / "clasi-version").exists(), (
            ".clasi/clasi-version must be removed by uninstall"
        )
