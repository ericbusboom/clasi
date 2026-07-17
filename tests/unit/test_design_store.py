"""Tests for clasi.design.store — persistent design doc set read/write."""

from __future__ import annotations

from pathlib import Path

import pytest

from clasi.design.store import (
    DesignDocSet,
    read_design_doc,
    read_doc_set,
    read_readme,
    read_system_doc,
    write_design_doc,
    write_readme,
    write_system_doc,
)
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


# ---------------------------------------------------------------------------
# write_design_doc / read_design_doc — round-trip
# ---------------------------------------------------------------------------


class TestDesignDocRoundTrip:
    def test_write_then_read_round_trips_content_and_frontmatter(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi", "tools")

        write_design_doc(project, subsystem, "# clasi.tools\n\nDoes things.\n")

        artifact = read_design_doc(project, subsystem)
        assert artifact.exists
        assert artifact.content == "# clasi.tools\n\nDoes things.\n"
        fm = artifact.frontmatter
        assert fm["source_paths"] == [str(subsystem)]
        assert fm["readme_path"] == str(subsystem / "README.md")

    def test_written_at_expected_slugified_path(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi", "tools")

        artifact = write_design_doc(project, subsystem, "content")

        assert artifact.path == project.design_dir / "clasi-tools.md"

    def test_extra_frontmatter_is_merged_and_does_not_override_required(
        self, tmp_path
    ):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")

        artifact = write_design_doc(
            project,
            subsystem,
            "content",
            extra_frontmatter={"source_paths": "should-not-win", "owner": "team-x"},
        )

        fm = artifact.frontmatter
        assert fm["source_paths"] == [str(subsystem)]
        assert fm["owner"] == "team-x"

    def test_overwrite_replaces_prior_content(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")

        write_design_doc(project, subsystem, "first version")
        write_design_doc(project, subsystem, "second version")

        artifact = read_design_doc(project, subsystem)
        assert artifact.content == "second version"


# ---------------------------------------------------------------------------
# write_system_doc / read_system_doc — round-trip
# ---------------------------------------------------------------------------


class TestSystemDocRoundTrip:
    def test_write_then_read_round_trips(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        (tmp_path / "src").mkdir()

        write_system_doc(project, "# System\n\nOverview.\n")

        artifact = read_system_doc(project)
        assert artifact.exists
        assert artifact.content == "# System\n\nOverview.\n"

    def test_written_at_design_md(self, tmp_path):
        project = _make_project(tmp_path, ["src"])

        artifact = write_system_doc(project, "content")

        assert artifact.path == project.design_dir / "design.md"

    def test_frontmatter_lists_all_source_roots(self, tmp_path):
        project = _make_project(tmp_path, ["src", "tests"])

        artifact = write_system_doc(project, "content")

        fm = artifact.frontmatter
        assert set(fm["source_paths"]) == {
            str((tmp_path / "src").resolve()),
            str((tmp_path / "tests").resolve()),
        }


# ---------------------------------------------------------------------------
# write_readme / read_readme — round-trip
# ---------------------------------------------------------------------------


class TestReadmeRoundTrip:
    def test_write_then_read_round_trips(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi", "tools")

        write_readme(
            subsystem,
            project,
            name="tools",
            description="MCP tool implementations.",
            content="# clasi.tools\n",
        )

        artifact = read_readme(subsystem)
        assert artifact.exists
        assert artifact.content == "# clasi.tools\n"
        fm = artifact.frontmatter
        assert fm["subsystem"] == "tools"
        assert fm["description"] == "MCP tool implementations."
        assert fm["design_doc_path"] == str(project.design_dir / "clasi-tools.md")

    def test_written_at_subsystem_readme_path(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")

        artifact = write_readme(
            subsystem, project, name="clasi", description="Root package."
        )

        assert artifact.path == subsystem / "README.md"

    def test_default_content_is_empty(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")

        artifact = write_readme(
            subsystem, project, name="clasi", description="Root package."
        )

        assert artifact.content == ""

    def test_extra_frontmatter_merged_without_overriding_required(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")

        artifact = write_readme(
            subsystem,
            project,
            name="clasi",
            description="Root package.",
            extra_frontmatter={"subsystem": "should-not-win", "maintainer": "eric"},
        )

        fm = artifact.frontmatter
        assert fm["subsystem"] == "clasi"
        assert fm["maintainer"] == "eric"

    def test_overwrite_replaces_prior_body(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")

        write_readme(
            subsystem, project, name="clasi", description="v1", content="first"
        )
        write_readme(
            subsystem, project, name="clasi", description="v2", content="second"
        )

        artifact = read_readme(subsystem)
        assert artifact.content == "second"
        assert artifact.frontmatter["description"] == "v2"


# ---------------------------------------------------------------------------
# read_doc_set — enumeration given a Project
# ---------------------------------------------------------------------------


class TestReadDocSetSingleRoot:
    def test_returns_design_doc_set_instance(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        (tmp_path / "src").mkdir()

        doc_set = read_doc_set(project)

        assert isinstance(doc_set, DesignDocSet)

    def test_system_doc_points_at_design_md(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        (tmp_path / "src").mkdir()

        doc_set = read_doc_set(project)

        assert doc_set.system_doc.path == project.design_dir / "design.md"

    def test_enumerates_one_entry_per_top_level_subsystem_dir(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        _make_subsystem(tmp_path, "src", "clasi", "tools")
        _make_subsystem(tmp_path, "src", "clasi", "schemas")
        root_clasi = (tmp_path / "src" / "clasi").resolve()

        doc_set = read_doc_set(project)

        # Only the immediate subdirectory of the source root ("clasi") is
        # a subsystem; nested dirs (tools, schemas) belong to it.
        assert set(doc_set.subsystem_docs.keys()) == {root_clasi}
        assert set(doc_set.readmes.keys()) == {root_clasi}

    def test_subsystem_doc_and_readme_paths_are_correct(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        _make_subsystem(tmp_path, "src", "clasi")
        root_clasi = (tmp_path / "src" / "clasi").resolve()

        doc_set = read_doc_set(project)

        assert doc_set.subsystem_docs[root_clasi].path == (
            project.design_dir / "clasi.md"
        )
        assert doc_set.readmes[root_clasi].path == root_clasi / "README.md"

    def test_handles_do_not_require_files_to_exist(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        _make_subsystem(tmp_path, "src", "clasi")

        doc_set = read_doc_set(project)

        assert not doc_set.system_doc.exists
        for artifact in doc_set.subsystem_docs.values():
            assert not artifact.exists
        for artifact in doc_set.readmes.values():
            assert not artifact.exists

    def test_empty_source_root_yields_no_subsystems(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        (tmp_path / "src").mkdir()

        doc_set = read_doc_set(project)

        assert doc_set.subsystem_docs == {}
        assert doc_set.readmes == {}

    def test_nonexistent_source_root_yields_no_subsystems(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        # src/ is never created on disk.

        doc_set = read_doc_set(project)

        assert doc_set.subsystem_docs == {}


class TestReadDocSetMultiRoot:
    def test_enumerates_subsystems_across_all_roots(self, tmp_path):
        project = _make_project(tmp_path, ["src", "tests"])
        _make_subsystem(tmp_path, "src", "clasi")
        _make_subsystem(tmp_path, "tests", "unit")
        _make_subsystem(tmp_path, "tests", "system")

        doc_set = read_doc_set(project)

        assert len(doc_set.subsystem_docs) == 3

    def test_multi_root_slugs_are_root_qualified(self, tmp_path):
        project = _make_project(tmp_path, ["src", "tests"])
        _make_subsystem(tmp_path, "src", "clasi")
        root_clasi = (tmp_path / "src" / "clasi").resolve()

        doc_set = read_doc_set(project)

        assert doc_set.subsystem_docs[root_clasi].path == (
            project.design_dir / "src-clasi.md"
        )


# ---------------------------------------------------------------------------
# Overwrite semantics documented, not merged
# ---------------------------------------------------------------------------


class TestOverwriteSemantics:
    def test_write_readme_does_not_preserve_body_by_default(self, tmp_path):
        """Re-bootstrapping without passing the old content silently
        replaces the body — this is the documented behavior, not a merge.
        A caller wanting to preserve hand-edits must read first and pass
        the preserved content explicitly."""
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")

        write_readme(
            subsystem,
            project,
            name="clasi",
            description="v1",
            content="hand-edited notes",
        )
        # Caller re-bootstraps without reading first.
        write_readme(subsystem, project, name="clasi", description="v2")

        artifact = read_readme(subsystem)
        assert artifact.content == ""

    def test_caller_can_preserve_existing_body_by_reading_first(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")

        write_readme(
            subsystem,
            project,
            name="clasi",
            description="v1",
            content="hand-edited notes",
        )
        existing = read_readme(subsystem)
        preserved_content = existing.content

        write_readme(
            subsystem,
            project,
            name="clasi",
            description="v2",
            content=preserved_content,
        )

        assert read_readme(subsystem).content == "hand-edited notes"
