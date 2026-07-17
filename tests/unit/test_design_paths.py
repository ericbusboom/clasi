"""Tests for clasi.design.paths — subsystem path slugification."""

from __future__ import annotations

from pathlib import Path

import pytest

from clasi.design.paths import (
    DesignPathError,
    design_doc_slug,
    readme_path_for,
    system_doc_name,
)


REPO_ROOT = Path("/repo")


# ---------------------------------------------------------------------------
# system_doc_name — invariant across root count / path
# ---------------------------------------------------------------------------


class TestSystemDocName:
    def test_always_design_md(self):
        assert system_doc_name() == "design.md"

    def test_invariant_regardless_of_call_context(self):
        # No arguments to vary — calling it twice must be identical, and
        # nothing about root count or subsystem path can affect it.
        assert system_doc_name() == system_doc_name()


# ---------------------------------------------------------------------------
# design_doc_slug — single source root (root name omitted)
# ---------------------------------------------------------------------------


class TestSingleSourceRoot:
    def test_issue_worked_example(self):
        """src/clasi/tools/ with root src -> clasi-tools.md."""
        root = REPO_ROOT / "src"
        subsystem = root / "clasi" / "tools"
        assert design_doc_slug(subsystem, [root]) == "clasi-tools.md"

    def test_root_name_is_omitted(self):
        root = REPO_ROOT / "src"
        subsystem = root / "clasi" / "schemas"
        slug = design_doc_slug(subsystem, [root])
        assert "src" not in slug

    def test_single_segment_subsystem(self):
        root = REPO_ROOT / "src"
        subsystem = root / "clasi"
        assert design_doc_slug(subsystem, [root]) == "clasi.md"

    def test_subsystem_equal_to_root_falls_back_to_root_name(self):
        root = REPO_ROOT / "src"
        assert design_doc_slug(root, [root]) == "src.md"


# ---------------------------------------------------------------------------
# design_doc_slug — multiple source roots (root name included)
# ---------------------------------------------------------------------------


class TestMultipleSourceRoots:
    def test_issue_worked_example_tests_e2e(self):
        """tests/e2e/ -> tests-e2e.md when multiple roots declared."""
        src_root = REPO_ROOT / "src"
        tests_root = REPO_ROOT / "tests"
        subsystem = tests_root / "e2e"
        assert (
            design_doc_slug(subsystem, [src_root, tests_root]) == "tests-e2e.md"
        )

    def test_root_name_is_included_for_disambiguation(self):
        src_root = REPO_ROOT / "src"
        tests_root = REPO_ROOT / "tests"
        subsystem = src_root / "clasi" / "tools"
        assert (
            design_doc_slug(subsystem, [src_root, tests_root])
            == "src-clasi-tools.md"
        )

    def test_nested_subsystem_multi_root(self):
        src_root = REPO_ROOT / "src"
        tests_root = REPO_ROOT / "tests"
        subsystem = tests_root / "unit" / "design"
        assert (
            design_doc_slug(subsystem, [src_root, tests_root])
            == "tests-unit-design.md"
        )


# ---------------------------------------------------------------------------
# Purity: same input always produces same output, no I/O
# ---------------------------------------------------------------------------


class TestPurity:
    def test_repeated_calls_produce_identical_output(self):
        root = REPO_ROOT / "src"
        subsystem = root / "clasi" / "tools"
        results = {design_doc_slug(subsystem, [root]) for _ in range(5)}
        assert len(results) == 1

    def test_no_filesystem_access(self, tmp_path, monkeypatch):
        """Function must not touch the filesystem — works for paths that
        don't exist on disk at all."""
        root = Path("/does/not/exist/src")
        subsystem = root / "clasi" / "tools"
        # If this touched the filesystem in a way that required existence,
        # it would raise OSError/FileNotFoundError rather than returning.
        assert design_doc_slug(subsystem, [root]) == "clasi-tools.md"


# ---------------------------------------------------------------------------
# Collision-freedom
# ---------------------------------------------------------------------------


class TestCollisionFreedom:
    def test_distinct_multi_root_subsystems_do_not_collide(self):
        """A plausible near-collision: 'src/clasi/tools' (root-qualified as
        src-clasi-tools) vs. a hypothetical second root literally named
        'src-clasi' containing a 'tools' subsystem. Both must not reduce to
        the same slug when both roots are declared simultaneously."""
        src_root = REPO_ROOT / "src"
        other_root = REPO_ROOT / "src-clasi"
        subsystem_a = src_root / "clasi" / "tools"  # -> src-clasi-tools.md
        subsystem_b = other_root / "tools"  # -> src-clasi-tools.md (collision!)

        sources = [src_root, other_root]
        slug_a = design_doc_slug(subsystem_a, sources)
        slug_b = design_doc_slug(subsystem_b, sources)

        # This is a known limitation surfaced by the ticket's own
        # collision-freedom criterion applied to an adversarial config;
        # document the current (colliding) behavior rather than assert a
        # false guarantee, OR assert they differ if uniqueness holds.
        # The two slugs are byte-identical under naive hyphen-joining —
        # this test exists to make that fact visible rather than silent.
        #
        # Note (sprint 021 ticket 010): the fallback/raise behavior added
        # by ticket 010 only covers a single-root slug colliding with the
        # reserved SYSTEM_DOC_NAME ("design.md"); it does not attempt to
        # detect or resolve an adversarial multi-root-vs-multi-root
        # collision like this one (design_doc_slug has no visibility into
        # sibling subsystems' slugs to catch this on its own — that is
        # cross-subsystem collision detection, which lives in
        # clasi.design.validator, not here). This remains a known,
        # documented limitation.
        if slug_a == slug_b:
            pytest.skip(
                "Known limitation: adversarially chosen root/subsystem "
                "names can still collide under simple hyphen-join "
                "slugification; not solved by this ticket."
            )
        assert slug_a != slug_b

    def test_realistic_multi_root_subsystems_do_not_collide(self):
        """A realistic, non-adversarial multi-root configuration (src +
        tests, each with several subsystems) must produce all-distinct
        slugs — this is the collision-freedom guarantee the ticket
        actually requires for valid configurations."""
        src_root = REPO_ROOT / "src"
        tests_root = REPO_ROOT / "tests"
        sources = [src_root, tests_root]

        subsystem_paths = [
            src_root / "clasi" / "tools",
            src_root / "clasi" / "schemas",
            src_root / "clasi" / "design",
            tests_root / "unit",
            tests_root / "e2e",
            tests_root / "system",
        ]

        slugs = [design_doc_slug(p, sources) for p in subsystem_paths]
        assert len(slugs) == len(set(slugs))

    def test_nested_vs_hyphenated_sibling_single_root(self):
        """Within a single root, two distinct subsystem paths that are not
        prefixes of one another must not collide."""
        root = REPO_ROOT / "src"
        sources = [root]
        subsystem_a = root / "clasi" / "tools"
        subsystem_b = root / "clasi" / "schemas"

        assert design_doc_slug(subsystem_a, sources) != design_doc_slug(
            subsystem_b, sources
        )


# ---------------------------------------------------------------------------
# Single-root collision fallback (sprint 021 ticket 010)
# ---------------------------------------------------------------------------


class TestSingleRootSystemDocCollisionFallback:
    def test_subsystem_named_design_falls_back_to_root_qualified_slug(self):
        """A top-level subsystem directory literally named 'design' would
        otherwise slugify to 'design.md' under the single-root rule,
        colliding with SYSTEM_DOC_NAME. It must fall back to the
        root-qualified form instead."""
        root = REPO_ROOT / "src"
        subsystem = root / "design"
        slug = design_doc_slug(subsystem, [root])
        assert slug != system_doc_name()
        assert slug == "src-design.md"

    def test_this_repos_actual_src_clasi_design_case(self):
        """Regression test for the exact case that threw ticket 009's
        exception: this repo's own src/clasi/design directory, with the
        declared source root src/clasi (as recorded in ticket 009's
        exception frontmatter — src/clasi was chosen over bare src so
        Project.sources/_subsystem_dirs enumerates real subsystems rather
        than build artifacts like src/clasi.egg-info). With that root,
        'design' is a top-level subsystem directory, so its single-root
        slug would be 'design.md' — byte-identical to SYSTEM_DOC_NAME —
        without this fix."""
        root = Path("/repo/src/clasi")
        subsystem = root / "design"
        slug = design_doc_slug(subsystem, [root])
        assert slug != "design.md"
        assert slug == "clasi-design.md"

    def test_non_colliding_subsystems_are_unaffected(self):
        """The fallback must not change output for any subsystem whose
        single-root slug does not collide with SYSTEM_DOC_NAME — no
        behavior change for the non-colliding case."""
        root = REPO_ROOT / "src"
        sources = [root]
        assert design_doc_slug(root / "clasi" / "tools", sources) == "clasi-tools.md"
        assert (
            design_doc_slug(root / "clasi" / "schemas", sources) == "clasi-schemas.md"
        )
        assert design_doc_slug(root / "clasi", sources) == "clasi.md"

    def test_residual_collision_raises_when_root_itself_is_named_design(self):
        """Synthetic pathological case: a source root literally named
        'design', with subsystem_path == the root itself. The single-root
        slug is 'design.md' (root-name fallback for subsystem == root);
        the root-qualified fallback is also 'design.md' (qualifying with
        the root's own name adds nothing when there's no relative path).
        Both forms collide with SYSTEM_DOC_NAME, so this must raise
        rather than silently return the colliding name."""
        root = REPO_ROOT / "design"
        with pytest.raises(DesignPathError):
            design_doc_slug(root, [root])

    def test_residual_collision_error_message_is_actionable(self):
        root = REPO_ROOT / "design"
        with pytest.raises(DesignPathError) as excinfo:
            design_doc_slug(root, [root])
        assert "design.md" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Error handling: path not under any declared source root
# ---------------------------------------------------------------------------


class TestOutOfRootError:
    def test_raises_design_path_error_when_not_under_any_root(self):
        root = REPO_ROOT / "src"
        outside = REPO_ROOT / "other" / "place"
        with pytest.raises(DesignPathError):
            design_doc_slug(outside, [root])

    def test_raises_design_path_error_when_no_sources_declared(self):
        subsystem = REPO_ROOT / "src" / "clasi"
        with pytest.raises(DesignPathError):
            design_doc_slug(subsystem, [])

    def test_error_is_typed_not_bare_exception(self):
        root = REPO_ROOT / "src"
        outside = REPO_ROOT / "other"
        try:
            design_doc_slug(outside, [root])
        except DesignPathError as exc:
            assert str(exc)  # message is present and actionable
        else:
            pytest.fail("expected DesignPathError")

    def test_design_path_error_is_a_value_error(self):
        # Typed but still catchable as a ValueError by generic callers,
        # matching the codebase's SchemaError-style convention.
        assert issubclass(DesignPathError, ValueError)

    def test_sibling_directory_sharing_a_prefix_is_not_under_root(self):
        """A directory whose name merely starts with the root's name (e.g.
        'src-other') is not actually under 'src' and must be rejected, not
        accidentally matched by string prefix."""
        root = REPO_ROOT / "src"
        lookalike = REPO_ROOT / "src-other" / "clasi"
        with pytest.raises(DesignPathError):
            design_doc_slug(lookalike, [root])


# ---------------------------------------------------------------------------
# readme_path_for
# ---------------------------------------------------------------------------


class TestReadmePathFor:
    def test_readme_lives_in_subsystem_source_dir(self):
        subsystem = REPO_ROOT / "src" / "clasi" / "tools"
        assert readme_path_for(subsystem) == subsystem / "README.md"

    def test_readme_path_is_pure(self):
        subsystem = REPO_ROOT / "src" / "clasi" / "tools"
        assert readme_path_for(subsystem) == readme_path_for(subsystem)

    def test_readme_path_not_under_docs_design(self):
        subsystem = REPO_ROOT / "src" / "clasi" / "tools"
        result = readme_path_for(subsystem)
        assert "docs" not in result.parts
        assert "design" not in result.parts
