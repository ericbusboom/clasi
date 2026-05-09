"""Tests for clasi.platforms._markers named-block API.

Covers write_named_section and strip_named_section round-trip semantics.
The existing write_section/strip_section functions are exercised by
integration tests elsewhere; this file focuses on the new named API.
"""

from pathlib import Path

import pytest

from clasi.platforms._markers import (
    write_named_section,
    strip_named_section,
    write_section,
    strip_section,
    write_version_stamp,
    remove_version_stamp,
    MARKER_START,
    MARKER_END,
)

RULES_START = "<!-- CLASI:RULES:START -->"
RULES_END = "<!-- CLASI:RULES:END -->"
CLASI_START = "<!-- CLASI:CLASI:START -->"
CLASI_END = "<!-- CLASI:CLASI:END -->"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_file(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# write_named_section — basic creation
# ---------------------------------------------------------------------------


class TestWriteNamedSectionCreatesFile:
    def test_creates_file_when_absent(self, tmp_path):
        p = tmp_path / "AGENTS.md"
        assert not p.exists()

        result = write_named_section(p, "RULES", "Do the thing.")

        assert result is True
        assert p.exists()
        text = p.read_text(encoding="utf-8")
        assert RULES_START in text
        assert "Do the thing." in text
        assert RULES_END in text

    def test_created_file_has_correct_structure(self, tmp_path):
        p = tmp_path / "AGENTS.md"
        write_named_section(p, "RULES", "rule content")

        text = p.read_text(encoding="utf-8")
        # START must precede END
        assert text.index(RULES_START) < text.index(RULES_END)
        # Content must be between the markers
        start_pos = text.index(RULES_START) + len(RULES_START)
        end_pos = text.index(RULES_END)
        inner = text[start_pos:end_pos]
        assert "rule content" in inner


# ---------------------------------------------------------------------------
# write_named_section — replace existing block
# ---------------------------------------------------------------------------


class TestWriteNamedSectionReplacesBlock:
    def test_replaces_block_in_place(self, tmp_path):
        p = tmp_path / "AGENTS.md"
        write_named_section(p, "RULES", "first content")
        result = write_named_section(p, "RULES", "second content")

        assert result is True
        text = p.read_text(encoding="utf-8")
        assert "second content" in text
        assert "first content" not in text
        # Exactly one pair of markers
        assert text.count(RULES_START) == 1
        assert text.count(RULES_END) == 1

    def test_does_not_touch_other_named_block(self, tmp_path):
        """Writing a RULES block must not disturb a pre-existing CLASI:START/END block."""
        p = tmp_path / "AGENTS.md"
        # Write the default CLASI:START/END block first using write_named_section
        write_named_section(p, "CLASI", "entry point content")
        original_text = p.read_text(encoding="utf-8")

        # Now write a RULES block
        write_named_section(p, "RULES", "rules content")

        text = p.read_text(encoding="utf-8")
        # CLASI block must be intact
        assert CLASI_START in text
        assert CLASI_END in text
        assert "entry point content" in text
        # RULES block must be present
        assert RULES_START in text
        assert "rules content" in text


# ---------------------------------------------------------------------------
# write_named_section — append to existing file
# ---------------------------------------------------------------------------


class TestWriteNamedSectionAppends:
    def test_appends_to_file_without_block(self, tmp_path):
        p = _make_file(tmp_path, "AGENTS.md", "User notes here.\n")

        result = write_named_section(p, "RULES", "rule content")

        assert result is True
        text = p.read_text(encoding="utf-8")
        assert "User notes here." in text
        assert RULES_START in text
        assert "rule content" in text
        assert RULES_END in text

    def test_user_content_preserved_when_appending(self, tmp_path):
        user_content = "# My notes\n\nDo not delete me.\n"
        p = _make_file(tmp_path, "AGENTS.md", user_content)
        write_named_section(p, "RULES", "rule content")

        text = p.read_text(encoding="utf-8")
        assert "Do not delete me." in text


# ---------------------------------------------------------------------------
# write_named_section — idempotent
# ---------------------------------------------------------------------------


class TestWriteNamedSectionIdempotent:
    def test_second_call_with_same_content_returns_false(self, tmp_path):
        p = tmp_path / "AGENTS.md"
        write_named_section(p, "RULES", "stable content")
        result = write_named_section(p, "RULES", "stable content")

        assert result is False

    def test_second_call_does_not_change_file(self, tmp_path):
        p = tmp_path / "AGENTS.md"
        write_named_section(p, "RULES", "stable content")
        text_before = p.read_text(encoding="utf-8")

        write_named_section(p, "RULES", "stable content")
        text_after = p.read_text(encoding="utf-8")

        assert text_before == text_after


# ---------------------------------------------------------------------------
# strip_named_section — basic removal
# ---------------------------------------------------------------------------


class TestStripNamedSectionRemovesTargetBlock:
    def test_removes_only_named_block(self, tmp_path):
        """strip RULES must not affect a CLASI block (or user content)."""
        p = tmp_path / "AGENTS.md"
        # Build file with two named blocks and user content
        write_named_section(p, "CLASI", "entry point content")
        write_named_section(p, "RULES", "rules content")
        # Prepend user content
        original = p.read_text(encoding="utf-8")
        p.write_text("User preamble.\n\n" + original, encoding="utf-8")

        result = strip_named_section(p, "RULES")

        assert result is True
        text = p.read_text(encoding="utf-8")
        # RULES block gone
        assert RULES_START not in text
        assert RULES_END not in text
        assert "rules content" not in text
        # CLASI block intact
        assert CLASI_START in text
        assert CLASI_END in text
        assert "entry point content" in text
        # User content intact
        assert "User preamble." in text

    def test_strip_absent_block_returns_false(self, tmp_path):
        p = _make_file(tmp_path, "AGENTS.md", "No managed blocks here.\n")

        result = strip_named_section(p, "RULES")

        assert result is False
        text = p.read_text(encoding="utf-8")
        assert text == "No managed blocks here.\n"

    def test_strip_nonexistent_file_returns_false(self, tmp_path):
        p = tmp_path / "missing.md"
        assert not p.exists()

        result = strip_named_section(p, "RULES")

        assert result is False

    def test_deletes_file_when_only_block_remains(self, tmp_path):
        p = tmp_path / "AGENTS.md"
        write_named_section(p, "RULES", "sole block content")

        result = strip_named_section(p, "RULES")

        assert result is True
        assert not p.exists()


# ---------------------------------------------------------------------------
# strip_named_section — does not affect other blocks
# ---------------------------------------------------------------------------


class TestStripNamedSectionDoesNotAffectOtherBlocks:
    def test_strip_rules_leaves_clasi_block(self, tmp_path):
        p = tmp_path / "AGENTS.md"
        write_named_section(p, "CLASI", "entry point")
        write_named_section(p, "RULES", "rules text")

        strip_named_section(p, "RULES")

        text = p.read_text(encoding="utf-8")
        assert CLASI_START in text
        assert "entry point" in text
        assert RULES_START not in text

    def test_strip_clasi_leaves_rules_block(self, tmp_path):
        p = tmp_path / "AGENTS.md"
        write_named_section(p, "CLASI", "entry point")
        write_named_section(p, "RULES", "rules text")

        strip_named_section(p, "CLASI")

        text = p.read_text(encoding="utf-8")
        assert RULES_START in text
        assert "rules text" in text
        assert CLASI_START not in text


# ---------------------------------------------------------------------------
# Full round-trip: two named blocks coexist
# ---------------------------------------------------------------------------


class TestTwoBlocksCoexistRoundTrip:
    def test_write_both_strip_one_other_survives(self, tmp_path):
        p = tmp_path / "AGENTS.md"
        user_preamble = "# Root AGENTS.md\n\nUser content.\n"
        p.write_text(user_preamble, encoding="utf-8")

        # Install both blocks
        write_named_section(p, "CLASI", "entry point instruction")
        write_named_section(p, "RULES", "global rules instruction")

        # Strip RULES — CLASI block and user content must survive
        strip_named_section(p, "RULES")

        text = p.read_text(encoding="utf-8")
        assert CLASI_START in text
        assert "entry point instruction" in text
        assert "User content." in text
        assert RULES_START not in text

        # Strip CLASI — file may be deleted or only have user preamble
        strip_named_section(p, "CLASI")

        if p.exists():
            text = p.read_text(encoding="utf-8")
            assert CLASI_START not in text
            assert RULES_START not in text
        # Either file is gone or has no CLASI-managed blocks

    def test_strip_then_reinstall_round_trips(self, tmp_path):
        p = tmp_path / "AGENTS.md"
        write_named_section(p, "CLASI", "entry v1")
        write_named_section(p, "RULES", "rules v1")

        # Update the RULES block
        write_named_section(p, "RULES", "rules v2")

        text = p.read_text(encoding="utf-8")
        assert "rules v2" in text
        assert "rules v1" not in text
        # CLASI block unchanged
        assert "entry v1" in text

    def test_named_api_with_name_clasi_matches_generic_markers(self, tmp_path):
        """write_named_section(..., 'CLASI', ...) writes CLASI:CLASI:START/END
        (not the legacy CLASI:START/END pair).  This test documents that the
        named API and the legacy write_section/strip_section are distinct.
        """
        p = tmp_path / "AGENTS.md"
        write_named_section(p, "CLASI", "named clasi content")

        text = p.read_text(encoding="utf-8")
        # Named API produces CLASI:CLASI:START/END markers
        assert "<!-- CLASI:CLASI:START -->" in text
        assert "<!-- CLASI:CLASI:END -->" in text
        # Legacy CLASI:START/END markers are NOT present
        assert MARKER_START not in text
        assert MARKER_END not in text


# ---------------------------------------------------------------------------
# write_version_stamp — consolidated .clasi/clasi-version
# ---------------------------------------------------------------------------


class TestWriteVersionStamp:
    def test_writes_clasi_clasi_version(self, tmp_path: Path) -> None:
        """write_version_stamp writes .clasi/clasi-version in the target root."""
        write_version_stamp(tmp_path)
        stamp = tmp_path / ".clasi" / "clasi-version"
        assert stamp.exists(), ".clasi/clasi-version must be created"

    def test_stamp_contains_version_string(self, tmp_path: Path) -> None:
        """Stamp file contains a non-empty version string followed by a newline."""
        write_version_stamp(tmp_path)
        stamp = tmp_path / ".clasi" / "clasi-version"
        content = stamp.read_text(encoding="utf-8")
        assert content.endswith("\n"), "Stamp must end with newline"
        assert content.strip(), "Version string must be non-empty"

    def test_idempotent_overwrite(self, tmp_path: Path) -> None:
        """Calling write_version_stamp twice on the same target does not raise."""
        write_version_stamp(tmp_path)
        write_version_stamp(tmp_path)
        stamp = tmp_path / ".clasi" / "clasi-version"
        assert stamp.exists()

    def test_creates_clasi_dir_if_absent(self, tmp_path: Path) -> None:
        """.clasi/ is created automatically if it does not exist."""
        assert not (tmp_path / ".clasi").exists()
        write_version_stamp(tmp_path)
        assert (tmp_path / ".clasi").is_dir()

    def test_no_per_platform_stamp_written(self, tmp_path: Path) -> None:
        """write_version_stamp must NOT write any per-platform .clasi-version files."""
        write_version_stamp(tmp_path)
        for stale_dir in [".claude", ".codex", ".agents", ".github"]:
            stale = tmp_path / stale_dir / ".clasi-version"
            assert not stale.exists(), (
                f"{stale_dir}/.clasi-version must not be written by write_version_stamp"
            )

    def test_removes_stale_claude_stamp(self, tmp_path: Path) -> None:
        """write_version_stamp removes a pre-existing .claude/.clasi-version."""
        stale = tmp_path / ".claude" / ".clasi-version"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("old-version\n", encoding="utf-8")

        write_version_stamp(tmp_path)

        assert not stale.exists(), ".claude/.clasi-version must be removed"

    def test_removes_stale_codex_stamp(self, tmp_path: Path) -> None:
        """write_version_stamp removes a pre-existing .codex/.clasi-version."""
        stale = tmp_path / ".codex" / ".clasi-version"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("old-version\n", encoding="utf-8")

        write_version_stamp(tmp_path)

        assert not stale.exists(), ".codex/.clasi-version must be removed"

    def test_removes_stale_agents_stamp(self, tmp_path: Path) -> None:
        """write_version_stamp removes a pre-existing .agents/.clasi-version."""
        stale = tmp_path / ".agents" / ".clasi-version"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("old-version\n", encoding="utf-8")

        write_version_stamp(tmp_path)

        assert not stale.exists(), ".agents/.clasi-version must be removed"

    def test_removes_stale_github_stamp(self, tmp_path: Path) -> None:
        """write_version_stamp removes a pre-existing .github/.clasi-version."""
        stale = tmp_path / ".github" / ".clasi-version"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("old-version\n", encoding="utf-8")

        write_version_stamp(tmp_path)

        assert not stale.exists(), ".github/.clasi-version must be removed"

    def test_no_error_when_stale_stamp_absent(self, tmp_path: Path) -> None:
        """write_version_stamp does not raise when no stale stamp files exist."""
        write_version_stamp(tmp_path)  # should not raise


# ---------------------------------------------------------------------------
# remove_version_stamp — uninstall cleanup
# ---------------------------------------------------------------------------


class TestRemoveVersionStamp:
    def test_removes_stamp_file(self, tmp_path: Path) -> None:
        """remove_version_stamp deletes .clasi/clasi-version if present."""
        write_version_stamp(tmp_path)
        assert (tmp_path / ".clasi" / "clasi-version").exists()

        remove_version_stamp(tmp_path)

        assert not (tmp_path / ".clasi" / "clasi-version").exists()

    def test_removes_empty_clasi_dir(self, tmp_path: Path) -> None:
        """remove_version_stamp removes .clasi/ when it becomes empty."""
        write_version_stamp(tmp_path)
        assert (tmp_path / ".clasi").exists()

        remove_version_stamp(tmp_path)

        assert not (tmp_path / ".clasi").exists(), (
            ".clasi/ must be removed when it becomes empty after stamp removal"
        )

    def test_preserves_clasi_dir_when_not_empty(self, tmp_path: Path) -> None:
        """.clasi/ is NOT removed when other files remain after stamp removal."""
        clasi_dir = tmp_path / ".clasi"
        clasi_dir.mkdir(parents=True, exist_ok=True)
        # Write the stamp
        stamp = clasi_dir / "clasi-version"
        stamp.write_text("v1\n", encoding="utf-8")
        # Add an unrelated file in .clasi/
        other = clasi_dir / "AGENTS.md"
        other.write_text("# rules\n", encoding="utf-8")

        remove_version_stamp(tmp_path)

        assert not stamp.exists(), "clasi-version must be removed"
        assert clasi_dir.exists(), ".clasi/ must survive (non-empty)"
        assert other.exists(), "AGENTS.md must be preserved"

    def test_noop_when_stamp_absent(self, tmp_path: Path) -> None:
        """remove_version_stamp is a no-op when .clasi/clasi-version does not exist."""
        remove_version_stamp(tmp_path)  # should not raise

    def test_round_trip_install_uninstall(self, tmp_path: Path) -> None:
        """write then remove leaves the target tree clean."""
        write_version_stamp(tmp_path)
        remove_version_stamp(tmp_path)

        assert not (tmp_path / ".clasi" / "clasi-version").exists()
        # .clasi/ itself must also be gone (was created solely for the stamp)
        assert not (tmp_path / ".clasi").exists()
