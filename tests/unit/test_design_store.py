"""Tests for clasi.design.store — co-located DESIGN.md doc set read/write."""

from __future__ import annotations

from pathlib import Path

from clasi.design.store import (
    DesignDocSet,
    read_design_doc,
    read_doc_set,
    read_system_doc,
    subsystem_template,
    write_design_doc,
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
    def test_write_then_read_round_trips_content_with_no_frontmatter(
        self, tmp_path
    ):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi", "tools")

        write_design_doc(project, subsystem, "# clasi.tools\n\nDoes things.\n")

        artifact = read_design_doc(project, subsystem)
        assert artifact.exists
        assert artifact.content == "# clasi.tools\n\nDoes things.\n"
        assert artifact.frontmatter == {}

    def test_write_produces_no_frontmatter_fence_on_disk(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")

        artifact = write_design_doc(project, subsystem, "# clasi\n")

        raw = artifact.path.read_text(encoding="utf-8")
        assert raw == "# clasi\n"
        assert not raw.startswith("---")

    def test_written_at_colocated_design_md_path(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi", "tools")

        artifact = write_design_doc(project, subsystem, "content")

        assert artifact.path == subsystem / "DESIGN.md"

    def test_extra_frontmatter_is_written_as_given(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")

        artifact = write_design_doc(
            project,
            subsystem,
            "content",
            extra_frontmatter={"owner": "team-x"},
        )

        fm = artifact.frontmatter
        assert fm == {"owner": "team-x"}
        assert artifact.content == "content"

    def test_overwrite_replaces_prior_content(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")

        write_design_doc(project, subsystem, "first version")
        write_design_doc(project, subsystem, "second version")

        artifact = read_design_doc(project, subsystem)
        assert artifact.content == "second version"

    def test_overwrite_from_frontmatter_to_bare_body_drops_fence(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")

        write_design_doc(
            project, subsystem, "content", extra_frontmatter={"owner": "team-x"}
        )
        write_design_doc(project, subsystem, "content")

        artifact = read_design_doc(project, subsystem)
        assert artifact.frontmatter == {}
        raw = artifact.path.read_text(encoding="utf-8")
        assert not raw.startswith("---")


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

    def test_frontmatter_has_no_readme_path_field(self, tmp_path):
        project = _make_project(tmp_path, ["src"])

        artifact = write_system_doc(project, "content")

        assert "readme_path" not in artifact.frontmatter


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

    def test_subsystem_doc_path_is_colocated_design_md(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        _make_subsystem(tmp_path, "src", "clasi")
        root_clasi = (tmp_path / "src" / "clasi").resolve()

        doc_set = read_doc_set(project)

        assert doc_set.subsystem_docs[root_clasi].path == root_clasi / "DESIGN.md"

    def test_handles_do_not_require_files_to_exist(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        _make_subsystem(tmp_path, "src", "clasi")

        doc_set = read_doc_set(project)

        assert not doc_set.system_doc.exists
        for artifact in doc_set.subsystem_docs.values():
            assert not artifact.exists

    def test_empty_source_root_yields_no_subsystems(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        (tmp_path / "src").mkdir()

        doc_set = read_doc_set(project)

        assert doc_set.subsystem_docs == {}

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

    def test_multi_root_subsystems_still_colocate_by_path(self, tmp_path):
        project = _make_project(tmp_path, ["src", "tests"])
        _make_subsystem(tmp_path, "src", "clasi")
        root_clasi = (tmp_path / "src" / "clasi").resolve()

        doc_set = read_doc_set(project)

        assert doc_set.subsystem_docs[root_clasi].path == root_clasi / "DESIGN.md"


# ---------------------------------------------------------------------------
# Overwrite semantics documented, not merged
# ---------------------------------------------------------------------------


class TestOverwriteSemantics:
    def test_write_design_doc_does_not_preserve_body_by_default(self, tmp_path):
        """Re-bootstrapping without passing the old content silently
        replaces the body — this is the documented behavior, not a merge.
        A caller wanting to preserve hand-edits must read first and pass
        the preserved content explicitly."""
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")

        write_design_doc(project, subsystem, "hand-edited notes")
        # Caller re-bootstraps without reading first.
        write_design_doc(project, subsystem, "")

        artifact = read_design_doc(project, subsystem)
        assert artifact.content == ""

    def test_caller_can_preserve_existing_body_by_reading_first(self, tmp_path):
        project = _make_project(tmp_path, ["src"])
        subsystem = _make_subsystem(tmp_path, "src", "clasi")

        write_design_doc(project, subsystem, "hand-edited notes")
        existing = read_design_doc(project, subsystem)
        preserved_content = existing.content

        write_design_doc(project, subsystem, preserved_content)

        assert read_design_doc(project, subsystem).content == "hand-edited notes"


# ---------------------------------------------------------------------------
# subsystem_template — packaged template resource
# ---------------------------------------------------------------------------


class TestSubsystemTemplate:
    def test_returns_nonempty_text(self):
        text = subsystem_template()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_preserves_html_comment_guidance_and_section_structure(self):
        text = subsystem_template()
        # HTML-comment guidance blocks are preserved, not stripped.
        assert "<!--" in text and "-->" in text
        # Section structure (1-6) survives the move into the package.
        for heading in (
            "## 1. Purpose",
            "## 2. Orientation",
            "## 3. Constraints and Invariants",
            "## 4. Design",
            "## 5. Interfaces",
            "## 6. Open Questions / Known Limitations",
        ):
            assert heading in text

    def test_matches_packaged_file_on_disk(self):
        from importlib import resources

        packaged_path = (
            resources.files("clasi.design.templates") / "subsystem-design.md"
        )
        assert subsystem_template() == packaged_path.read_text(encoding="utf-8")
