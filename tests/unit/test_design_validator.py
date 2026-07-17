"""Tests for clasi.design.validator — co-located doc set and sprint overlay validation."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from clasi.design.store import write_design_doc, write_system_doc
from clasi.design.validator import DesignError, validate, validate_or_raise
from clasi.project import Project


def _make_project(tmp_path: Path, sources: list[str]) -> Project:
    config_dir = tmp_path / ".clasi"
    config_dir.mkdir(parents=True, exist_ok=True)
    sources_yaml = "\n".join(f"  - {s}" for s in sources)
    (config_dir / "config.yaml").write_text(
        f"sources:\n{sources_yaml}\n", encoding="utf-8"
    )
    return Project(tmp_path)


def _make_subsystem(tmp_path: Path, *parts: str) -> Path:
    subsystem = tmp_path.joinpath(*parts)
    subsystem.mkdir(parents=True, exist_ok=True)
    return subsystem.resolve()


def _write_valid_doc_set(tmp_path: Path) -> Project:
    """Build a project with one source root, one subsystem, fully linked."""
    project = _make_project(tmp_path, ["src"])
    subsystem = _make_subsystem(tmp_path, "src", "clasi")

    write_system_doc(project, "# System design\n")
    write_design_doc(project, subsystem, "# clasi subsystem\n")

    return project


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestValidDocSet:
    def test_valid_doc_set_passes(self, tmp_path):
        project = _write_valid_doc_set(tmp_path)
        result = validate(project)
        assert result.ok
        assert result.messages == []

    def test_validate_or_raise_does_not_raise(self, tmp_path):
        project = _write_valid_doc_set(tmp_path)
        validate_or_raise(project)  # should not raise


# ---------------------------------------------------------------------------
# Failure mode 1: missing design.md
# ---------------------------------------------------------------------------


class TestMissingSystemDoc:
    def test_missing_design_md_is_flagged(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")
        write_design_doc(project, subsystem, "# clasi subsystem\n")
        # system doc intentionally not written

        result = validate(project)
        assert not result.ok
        assert any("Missing top-level design document" in m for m in result.messages)

    def test_validate_or_raise_raises_design_error(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")
        write_design_doc(project, subsystem, "content")

        with pytest.raises(DesignError, match="Missing top-level design document"):
            validate_or_raise(project)


# ---------------------------------------------------------------------------
# Failure mode 2: unmapped source root (subsystem dir with no doc)
# ---------------------------------------------------------------------------


class TestUnmappedSourceRoot:
    def test_subsystem_with_no_design_doc_is_flagged(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        # Subsystem directory exists on disk but no design doc written for it.
        _make_subsystem(tmp_path, "src", "orphan_subsystem")
        write_system_doc(project, "# System design\n")

        result = validate(project)
        assert not result.ok
        assert any("Missing design doc" in m for m in result.messages)
        assert any("orphan_subsystem" in m for m in result.messages)


# ---------------------------------------------------------------------------
# Failure mode 3: DESIGN.md present but empty / whitespace-only
# ---------------------------------------------------------------------------


class TestEmptyDesignDoc:
    def test_empty_design_doc_is_flagged(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")
        write_system_doc(project, "# System design\n")
        doc = write_design_doc(project, subsystem, "# clasi subsystem\n")
        doc.path.write_text("", encoding="utf-8")

        result = validate(project)
        assert not result.ok
        assert any("Empty design doc" in m for m in result.messages)

    def test_whitespace_only_design_doc_is_flagged(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")
        write_system_doc(project, "# System design\n")
        doc = write_design_doc(project, subsystem, "# clasi subsystem\n")
        doc.path.write_text("   \n\n\t\n", encoding="utf-8")

        result = validate(project)
        assert not result.ok
        assert any("Empty design doc" in m for m in result.messages)

    def test_non_empty_design_doc_passes(self, tmp_path):
        project = _write_valid_doc_set(tmp_path)
        result = validate(project)
        assert result.ok


# ---------------------------------------------------------------------------
# The 5 project-level docs/design/*.md docs remain informational-only —
# never orphan-errors, but surfaced via ValidationResult.info.
# ---------------------------------------------------------------------------


class TestProjectLevelDocsInformationalOnly:
    def test_five_frozen_initiation_docs_alongside_subsystem_docs_validates_clean(
        self, tmp_path
    ):
        """Matches this repo's actual post-migration docs/design/ shape:
        five project-level docs coexisting with a correct co-located
        subsystem doc set and the system doc."""
        project = _write_valid_doc_set(tmp_path)
        for name in (
            "overview.md",
            "specification.md",
            "usecases.md",
            "state-machines.md",
            "worktree-process.md",
        ):
            (project.design_dir / name).write_text(
                f"# {name}\n\nProject-level doc, no frontmatter.\n",
                encoding="utf-8",
            )

        result = validate(project)
        assert result.ok
        assert result.messages == []
        assert len(result.info) == 5

    def test_project_level_doc_produces_info_entry_not_error(self, tmp_path):
        project = _write_valid_doc_set(tmp_path)
        (project.design_dir / "overview.md").write_text(
            "# Overview\n\nNo frontmatter.\n", encoding="utf-8"
        )

        result = validate(project)
        assert result.ok
        assert not any("Orphaned design doc" in m for m in result.messages)
        assert any(
            "overview.md" in i and "not orphan-checked" in i for i in result.info
        )


# ---------------------------------------------------------------------------
# Orphaned docs: stray DESIGN.md not matching a recognized subsystem path
# ---------------------------------------------------------------------------


class TestOrphanedStrayDesignDoc:
    def test_design_md_nested_too_deep_is_flagged(self, tmp_path):
        """A DESIGN.md placed under a subsystem's own subdirectory (not
        the subsystem root itself) is a stray orphan, not a subsystem
        doc — store._subsystem_dirs only enumerates immediate
        subdirectories of a source root as subsystems."""
        project = _write_valid_doc_set(tmp_path)
        nested_dir = tmp_path / "src" / "clasi" / "nested"
        nested_dir.mkdir(parents=True)
        (nested_dir / "DESIGN.md").write_text("# stray\n", encoding="utf-8")

        result = validate(project)
        assert not result.ok
        assert any(
            "Orphaned design doc" in m and "nested" in m for m in result.messages
        )

    def test_valid_subsystem_docs_are_never_flagged_as_orphans(self, tmp_path):
        project = _write_valid_doc_set(tmp_path)
        result = validate(project)
        assert not any("Orphaned design doc" in m for m in result.messages)


# ---------------------------------------------------------------------------
# Sprint overlay — stale or missing .diff.md
# ---------------------------------------------------------------------------


class TestSprintOverlay:
    def test_overlay_missing_diff_md_is_flagged(self, tmp_path):
        project = _write_valid_doc_set(tmp_path)
        overlay_dir = tmp_path / "clasi" / "sprints" / "001-x" / "design"
        overlay_dir.mkdir(parents=True)
        (overlay_dir / "design.md").write_text(
            "---\nsource_paths: []\n---\nUpdated system design.\n", encoding="utf-8"
        )

        result = validate(project, overlay_dir)
        assert not result.ok
        assert any("no corresponding" in m for m in result.messages)

    def test_overlay_with_fresh_diff_passes(self, tmp_path):
        project = _write_valid_doc_set(tmp_path)
        overlay_dir = tmp_path / "clasi" / "sprints" / "001-x" / "design"
        overlay_dir.mkdir(parents=True)
        content = "---\nsource_paths: []\n---\nUpdated system design.\n"
        (overlay_dir / "design.md").write_text(content, encoding="utf-8")

        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        (overlay_dir / "design.diff.md").write_text(
            f"---\nsource_hash: {digest}\n---\nDiff body.\n", encoding="utf-8"
        )

        result = validate(project, overlay_dir)
        assert result.ok

    def test_overlay_with_stale_diff_is_flagged(self, tmp_path):
        project = _write_valid_doc_set(tmp_path)
        overlay_dir = tmp_path / "clasi" / "sprints" / "001-x" / "design"
        overlay_dir.mkdir(parents=True)
        content = "---\nsource_paths: []\n---\nUpdated system design.\n"
        (overlay_dir / "design.md").write_text(content, encoding="utf-8")

        stale_digest = hashlib.sha256(b"stale content").hexdigest()
        (overlay_dir / "design.diff.md").write_text(
            f"---\nsource_hash: {stale_digest}\n---\nDiff body.\n", encoding="utf-8"
        )

        result = validate(project, overlay_dir)
        assert not result.ok
        assert any("is stale" in m for m in result.messages)

    def test_overlay_filename_not_matching_canonical_doc_is_flagged(self, tmp_path):
        project = _write_valid_doc_set(tmp_path)
        overlay_dir = tmp_path / "clasi" / "sprints" / "001-x" / "design"
        overlay_dir.mkdir(parents=True)
        content = "---\nsource_paths: []\n---\nBody.\n"
        (overlay_dir / "unknown-subsystem.md").write_text(content, encoding="utf-8")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        (overlay_dir / "unknown-subsystem.diff.md").write_text(
            f"---\nsource_hash: {digest}\n---\nDiff.\n", encoding="utf-8"
        )

        result = validate(project, overlay_dir)
        assert not result.ok
        assert any("does not match any existing canonical" in m for m in result.messages)

    def test_overlay_matching_a_subsystem_doc_filename_passes(self, tmp_path):
        """DESIGN.md is a valid overlay filename target once a subsystem
        doc exists with that name (co-located model, ticket 004)."""
        project = _write_valid_doc_set(tmp_path)
        overlay_dir = tmp_path / "clasi" / "sprints" / "001-x" / "design"
        overlay_dir.mkdir(parents=True)
        content = "# Updated clasi subsystem\n"
        (overlay_dir / "DESIGN.md").write_text(content, encoding="utf-8")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        (overlay_dir / "DESIGN.diff.md").write_text(
            f"---\nsource_hash: {digest}\n---\nDiff.\n", encoding="utf-8"
        )

        result = validate(project, overlay_dir)
        assert result.ok

    def test_missing_overlay_directory_is_flagged(self, tmp_path):
        project = _write_valid_doc_set(tmp_path)
        overlay_dir = tmp_path / "clasi" / "sprints" / "999-missing" / "design"

        result = validate(project, overlay_dir)
        assert not result.ok
        assert any("does not exist" in m for m in result.messages)


# ---------------------------------------------------------------------------
# No collision logic remains (co-located docs cannot collide)
# ---------------------------------------------------------------------------


class TestNoCollisionLogic:
    def test_distinct_subsystems_never_collide(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        sub_a = _make_subsystem(tmp_path, "src", "alpha")
        sub_b = _make_subsystem(tmp_path, "src", "beta")
        write_system_doc(project, "# System design\n")
        write_design_doc(project, sub_a, "# alpha\n")
        write_design_doc(project, sub_b, "# beta\n")

        result = validate(project)
        assert result.ok
        assert not any("collision" in m.lower() for m in result.messages)

    def test_subsystem_named_design_does_not_collide_with_system_doc(self, tmp_path):
        """A subsystem literally named 'design' resolves to
        <path>/DESIGN.md — a different filename/path from the system
        doc's docs/design/design.md, so no collision is possible."""
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "design")
        write_system_doc(project, "# System design\n")
        write_design_doc(project, subsystem, "# design subsystem\n")

        result = validate(project)
        assert result.ok


# ---------------------------------------------------------------------------
# Collect-all-failures behavior
# ---------------------------------------------------------------------------


class TestCollectsAllFailures:
    def test_multiple_independent_failures_all_reported(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        # No system doc, no subsystem docs at all -> only "missing design.md"
        # since there are no subsystem dirs to be unmapped. Add an orphan dir
        # to get a second, independent failure.
        _make_subsystem(tmp_path, "src", "orphan")

        result = validate(project)
        assert not result.ok
        assert len(result.messages) >= 2

    def test_cli_and_mcp_surface_messages_identically(self, tmp_path):
        """validate() and validate_or_raise() must produce equivalent
        results, per the module's CLI/MCP-equivalence contract."""
        project = _make_project(tmp_path, ["src"])
        _make_subsystem(tmp_path, "src", "orphan")

        result = validate(project)
        with pytest.raises(DesignError) as excinfo:
            validate_or_raise(project)

        assert set(result.messages) == set(str(excinfo.value).split("\n"))
