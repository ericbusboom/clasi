"""Tests for clasi.design.validator — doc set and sprint overlay validation."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from clasi.design.store import write_design_doc, write_readme, write_system_doc
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
    write_readme(subsystem, project, name="clasi", description="The clasi package.")

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
        write_readme(subsystem, project, name="clasi", description="desc")
        # system doc intentionally not written

        result = validate(project)
        assert not result.ok
        assert any("Missing top-level design document" in m for m in result.messages)

    def test_validate_or_raise_raises_design_error(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")
        write_design_doc(project, subsystem, "content")
        write_readme(subsystem, project, name="clasi", description="desc")

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
        assert any("Unmapped source root" in m for m in result.messages)
        assert any("orphan_subsystem" in m for m in result.messages)


# ---------------------------------------------------------------------------
# Failure mode 3: design doc <-> README backlink, both directions
# ---------------------------------------------------------------------------


class TestBacklinkFailures:
    def test_design_doc_with_no_readme_backlink(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")
        write_system_doc(project, "# System design\n")
        write_design_doc(project, subsystem, "# clasi subsystem\n")
        # README intentionally not written.

        result = validate(project)
        assert not result.ok
        assert any(
            "has no README.md" in m or "no design_doc_path" in m
            for m in result.messages
        )

    def test_readme_with_no_design_doc_side_reference(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")
        write_system_doc(project, "# System design\n")
        write_readme(subsystem, project, name="clasi", description="desc")
        # Design doc intentionally not written -> "unmapped source root"
        # fires, but we also want to exercise the reverse-direction check
        # directly: write the design doc but strip its readme_path.
        doc = write_design_doc(project, subsystem, "# clasi subsystem\n")
        fm, body = doc.read_document()
        fm["readme_path"] = None
        doc.write(fm, body)

        result = validate(project)
        assert not result.ok
        assert any("has no readme_path" in m for m in result.messages)

    def test_readme_referencing_nonexistent_design_doc(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")
        write_system_doc(project, "# System design\n")
        write_design_doc(project, subsystem, "# clasi subsystem\n")
        readme = write_readme(subsystem, project, name="clasi", description="desc")
        fm, body = readme.read_document()
        fm["design_doc_path"] = str(project.design_dir / "does-not-exist.md")
        readme.write(fm, body)

        result = validate(project)
        assert not result.ok
        assert any("does not exist" in m for m in result.messages)


# ---------------------------------------------------------------------------
# Orphaned docs
# ---------------------------------------------------------------------------


class TestOrphanedDocs:
    def test_orphaned_design_doc_is_flagged(self, tmp_path):
        project = _write_valid_doc_set(tmp_path)
        orphan = project.design_dir / "no-such-subsystem.md"
        orphan.write_text("---\nsource_paths: []\n---\nOrphan.\n", encoding="utf-8")

        result = validate(project)
        assert not result.ok
        assert any("Orphaned design doc" in m for m in result.messages)


# ---------------------------------------------------------------------------
# Failure mode 4: sprint overlay — stale or missing .diff.md
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

    def test_missing_overlay_directory_is_flagged(self, tmp_path):
        project = _write_valid_doc_set(tmp_path)
        overlay_dir = tmp_path / "clasi" / "sprints" / "999-missing" / "design"

        result = validate(project, overlay_dir)
        assert not result.ok
        assert any("does not exist" in m for m in result.messages)


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
