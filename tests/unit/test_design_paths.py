"""Tests for clasi.design.paths — co-located DESIGN.md path resolution."""

from __future__ import annotations

from pathlib import Path

from clasi.design.paths import design_doc_path_for, system_doc_name


REPO_ROOT = Path("/repo")


# ---------------------------------------------------------------------------
# system_doc_name — invariant across subsystem path / source-root count
# ---------------------------------------------------------------------------


class TestSystemDocName:
    def test_always_design_md(self):
        assert system_doc_name() == "design.md"

    def test_invariant_regardless_of_call_context(self):
        # No arguments to vary — calling it twice must be identical, and
        # nothing about a subsystem path can affect it.
        assert system_doc_name() == system_doc_name()


# ---------------------------------------------------------------------------
# design_doc_path_for — co-located DESIGN.md resolution
# ---------------------------------------------------------------------------


class TestDesignDocPathFor:
    def test_single_subsystem(self):
        subsystem = REPO_ROOT / "src" / "clasi" / "tools"
        assert design_doc_path_for(subsystem) == subsystem / "DESIGN.md"

    def test_nested_source_root(self):
        subsystem = REPO_ROOT / "tests" / "unit" / "design"
        assert design_doc_path_for(subsystem) == subsystem / "DESIGN.md"

    def test_subsystem_path_equal_to_a_source_root(self):
        """No source-root concept is involved any more — a subsystem path
        that happens to equal what was previously a declared source root
        resolves the same way as any other path."""
        root = REPO_ROOT / "src"
        assert design_doc_path_for(root) == root / "DESIGN.md"

    def test_subsystem_named_design_does_not_collide_with_system_doc(self):
        """A subsystem literally named 'design' (e.g. this repo's own
        src/clasi/design) previously required collision-fallback handling
        against the reserved 'design.md' system-doc name. That collision
        cannot happen any more: the subsystem's doc is
        'src/clasi/design/DESIGN.md', which is a different filename
        (DESIGN.md, uppercase) at a different path entirely from any
        'design.md' the system doc might occupy."""
        subsystem = REPO_ROOT / "src" / "clasi" / "design"
        result = design_doc_path_for(subsystem)
        assert result == subsystem / "DESIGN.md"
        assert result.name != system_doc_name()

    def test_purity_repeated_calls_produce_identical_output(self):
        subsystem = REPO_ROOT / "src" / "clasi" / "tools"
        results = {design_doc_path_for(subsystem) for _ in range(5)}
        assert len(results) == 1

    def test_no_filesystem_access(self):
        """Function must not touch the filesystem — works for paths that
        don't exist on disk at all."""
        subsystem = Path("/does/not/exist/src/clasi/tools")
        assert design_doc_path_for(subsystem) == subsystem / "DESIGN.md"

    def test_distinct_subsystems_do_not_collide(self):
        """Every subsystem has its own directory, so distinct subsystem
        paths always produce distinct DESIGN.md paths — no shared flat
        namespace to collide within."""
        subsystem_a = REPO_ROOT / "src" / "clasi" / "tools"
        subsystem_b = REPO_ROOT / "src" / "clasi" / "schemas"
        assert design_doc_path_for(subsystem_a) != design_doc_path_for(subsystem_b)

    def test_result_lives_inside_subsystem_directory(self):
        subsystem = REPO_ROOT / "src" / "clasi" / "tools"
        result = design_doc_path_for(subsystem)
        assert result.parent == subsystem
        assert "docs" not in result.parts
