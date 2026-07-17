"""Tests for the sources: list and design_docs opt-in config (sprint 021, ticket 001)."""

from __future__ import annotations

from pathlib import Path

import pytest

from clasi.project import (
    Project,
    _load_config,
    _load_design_docs_opt_in,
    _load_sources_config,
)


# ---------------------------------------------------------------------------
# _load_config — module-level helper
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_returns_empty_dict_when_no_config(self, tmp_path):
        assert _load_config(tmp_path) == {}

    def test_returns_full_parsed_mapping(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "process: se\nsources:\n  - src\n", encoding="utf-8"
        )
        data = _load_config(tmp_path)
        assert data == {"process": "se", "sources": ["src"]}

    def test_returns_empty_dict_for_malformed_yaml(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "---bad\nmalformed: [yaml\n", encoding="utf-8"
        )
        assert _load_config(tmp_path) == {}

    def test_returns_empty_dict_when_top_level_not_dict(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "- item1\n- item2\n", encoding="utf-8"
        )
        assert _load_config(tmp_path) == {}


# ---------------------------------------------------------------------------
# _load_sources_config
# ---------------------------------------------------------------------------


class TestLoadSourcesConfig:
    def test_returns_empty_list_when_no_config(self, tmp_path):
        assert _load_sources_config(tmp_path) == []

    def test_returns_empty_list_when_no_sources_key(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("process: se\n", encoding="utf-8")
        assert _load_sources_config(tmp_path) == []

    def test_returns_single_source(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "sources:\n  - src\n", encoding="utf-8"
        )
        assert _load_sources_config(tmp_path) == ["src"]

    def test_returns_multiple_sources_in_order(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "sources:\n  - src\n  - tests\n", encoding="utf-8"
        )
        assert _load_sources_config(tmp_path) == ["src", "tests"]

    def test_returns_empty_list_when_sources_not_a_list(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "sources: src\n", encoding="utf-8"
        )
        assert _load_sources_config(tmp_path) == []

    def test_returns_empty_list_for_malformed_yaml(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "---bad\nmalformed: [yaml\n", encoding="utf-8"
        )
        assert _load_sources_config(tmp_path) == []


# ---------------------------------------------------------------------------
# _load_design_docs_opt_in
# ---------------------------------------------------------------------------


class TestLoadDesignDocsOptIn:
    def test_returns_none_when_no_config(self, tmp_path):
        assert _load_design_docs_opt_in(tmp_path) is None

    def test_returns_none_when_key_absent(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("process: se\n", encoding="utf-8")
        assert _load_design_docs_opt_in(tmp_path) is None

    def test_returns_enabled(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "design_docs: enabled\n", encoding="utf-8"
        )
        assert _load_design_docs_opt_in(tmp_path) == "enabled"

    def test_returns_disabled(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "design_docs: disabled\n", encoding="utf-8"
        )
        assert _load_design_docs_opt_in(tmp_path) == "disabled"

    def test_returns_none_for_malformed_yaml(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "---bad\nmalformed: [yaml\n", encoding="utf-8"
        )
        assert _load_design_docs_opt_in(tmp_path) is None


# ---------------------------------------------------------------------------
# Project.sources
# ---------------------------------------------------------------------------


class TestProjectSources:
    def test_empty_when_no_config(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.sources == []

    def test_empty_when_sources_key_absent(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("process: se\n", encoding="utf-8")
        proj = Project(tmp_path)
        assert proj.sources == []

    def test_single_source_resolved_absolute(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "sources:\n  - src\n", encoding="utf-8"
        )
        proj = Project(tmp_path)
        result = proj.sources
        assert result == [(tmp_path / "src").resolve()]
        assert all(isinstance(p, Path) for p in result)
        assert all(p.is_absolute() for p in result)

    def test_multiple_sources_resolved_in_order(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "sources:\n  - src\n  - tests\n", encoding="utf-8"
        )
        proj = Project(tmp_path)
        result = proj.sources
        assert result == [
            (tmp_path / "src").resolve(),
            (tmp_path / "tests").resolve(),
        ]

    def test_single_vs_multiple_derivable_from_length(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "sources:\n  - src\n", encoding="utf-8"
        )
        proj_single = Project(tmp_path)
        assert len(proj_single.sources) == 1

        tmp_path2 = tmp_path / "other"
        tmp_path2.mkdir()
        config_dir2 = tmp_path2 / ".clasi"
        config_dir2.mkdir()
        (config_dir2 / "config.yaml").write_text(
            "sources:\n  - src\n  - tests\n", encoding="utf-8"
        )
        proj_multi = Project(tmp_path2)
        assert len(proj_multi.sources) == 2

    def test_lazy_cache(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "sources:\n  - src\n", encoding="utf-8"
        )
        proj = Project(tmp_path)
        first = proj.sources
        second = proj.sources
        assert first == second


# ---------------------------------------------------------------------------
# Project.design_docs_opt_in
# ---------------------------------------------------------------------------


class TestProjectDesignDocsOptIn:
    def test_unset_when_no_config(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.design_docs_opt_in is None

    def test_unset_when_key_absent(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("process: se\n", encoding="utf-8")
        proj = Project(tmp_path)
        assert proj.design_docs_opt_in is None

    def test_true_when_enabled(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "design_docs: enabled\n", encoding="utf-8"
        )
        proj = Project(tmp_path)
        assert proj.design_docs_opt_in is True

    def test_false_when_disabled(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "design_docs: disabled\n", encoding="utf-8"
        )
        proj = Project(tmp_path)
        assert proj.design_docs_opt_in is False

    def test_none_distinguishable_from_false(self, tmp_path):
        """Unset must not be conflated with explicit opt-out."""
        unset_root = tmp_path / "unset_project"
        unset_root.mkdir()
        proj_unset = Project(unset_root)
        assert proj_unset.design_docs_opt_in is None

        disabled_root = tmp_path / "disabled_project"
        config_dir = disabled_root / ".clasi"
        config_dir.mkdir(parents=True)
        (config_dir / "config.yaml").write_text(
            "design_docs: disabled\n", encoding="utf-8"
        )
        proj_disabled = Project(disabled_root)
        assert proj_disabled.design_docs_opt_in is False
        assert proj_unset.design_docs_opt_in is None
        assert proj_disabled.design_docs_opt_in is not None


# ---------------------------------------------------------------------------
# Project.set_design_docs_opt_in — round-trip
# ---------------------------------------------------------------------------


class TestSetDesignDocsOptIn:
    def test_round_trip_enabled(self, tmp_path):
        proj = Project(tmp_path)
        proj.set_design_docs_opt_in(True)

        fresh = Project(tmp_path)
        assert fresh.design_docs_opt_in is True

    def test_round_trip_disabled(self, tmp_path):
        proj = Project(tmp_path)
        proj.set_design_docs_opt_in(False)

        fresh = Project(tmp_path)
        assert fresh.design_docs_opt_in is False

    def test_creates_config_when_missing(self, tmp_path):
        proj = Project(tmp_path)
        assert not (tmp_path / ".clasi" / "config.yaml").exists()
        proj.set_design_docs_opt_in(True)
        assert (tmp_path / ".clasi" / "config.yaml").exists()

    def test_preserves_existing_keys(self, tmp_path):
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "process: se\npaths:\n  issues: myteam/issues\n", encoding="utf-8"
        )
        proj = Project(tmp_path)
        proj.set_design_docs_opt_in(True)

        fresh = Project(tmp_path)
        assert fresh.design_docs_opt_in is True
        assert fresh.issues_dir == tmp_path / "myteam" / "issues"

    def test_overwrites_previous_decision(self, tmp_path):
        proj = Project(tmp_path)
        proj.set_design_docs_opt_in(True)
        proj.set_design_docs_opt_in(False)

        fresh = Project(tmp_path)
        assert fresh.design_docs_opt_in is False
