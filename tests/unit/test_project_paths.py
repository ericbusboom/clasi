"""Tests for the configurable path layer in Project."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from clasi.project import (
    ARTIFACT_PATH_DEFAULTS,
    Project,
    _load_paths_config,
)


# ---------------------------------------------------------------------------
# _load_paths_config — module-level function
# ---------------------------------------------------------------------------


class TestLoadPathsConfig:
    """Unit tests for _load_paths_config."""

    def test_returns_empty_dict_when_no_config(self, tmp_path):
        """Missing config.yaml → empty dict."""
        result = _load_paths_config(tmp_path)
        assert result == {}

    def test_returns_paths_dict_when_present(self, tmp_path):
        """Valid paths: map is returned."""
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "process: se\npaths:\n  issues: myteam/issues\n", encoding="utf-8"
        )
        result = _load_paths_config(tmp_path)
        assert result == {"issues": "myteam/issues"}

    def test_returns_empty_dict_for_malformed_yaml(self, tmp_path):
        """Corrupt YAML → empty dict, no exception."""
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "---bad\nmalformed: [yaml\n", encoding="utf-8"
        )
        result = _load_paths_config(tmp_path)
        assert result == {}

    def test_returns_empty_dict_when_paths_is_not_dict(self, tmp_path):
        """paths: "string" → empty dict."""
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "paths: just-a-string\n", encoding="utf-8"
        )
        result = _load_paths_config(tmp_path)
        assert result == {}

    def test_returns_empty_dict_when_no_paths_key(self, tmp_path):
        """Config without paths: key → empty dict."""
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "process: se\n", encoding="utf-8"
        )
        result = _load_paths_config(tmp_path)
        assert result == {}

    def test_returns_empty_dict_when_data_is_not_dict(self, tmp_path):
        """Top-level YAML is a list, not dict → empty dict."""
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "- item1\n- item2\n", encoding="utf-8"
        )
        result = _load_paths_config(tmp_path)
        assert result == {}


# ---------------------------------------------------------------------------
# Project path properties — default (no config)
# ---------------------------------------------------------------------------


class TestDefaultPaths:
    """Test Project path properties with no config.yaml present."""

    def test_default_paths_no_config_issues(self, tmp_path):
        """issues_dir returns new default when no config.yaml."""
        proj = Project(tmp_path)
        assert proj.issues_dir == tmp_path / "clasi" / "issues"

    def test_default_paths_no_config_sprints(self, tmp_path):
        """sprints_dir returns new default when no config.yaml."""
        proj = Project(tmp_path)
        assert proj.sprints_dir == tmp_path / "clasi" / "sprints"

    def test_default_paths_no_config_reflections(self, tmp_path):
        """reflections_dir returns new default when no config.yaml."""
        proj = Project(tmp_path)
        assert proj.reflections_dir == tmp_path / "clasi" / "reflections"

    def test_default_paths_no_config_architecture(self, tmp_path):
        """architecture_dir returns new default when no config.yaml."""
        proj = Project(tmp_path)
        assert proj.architecture_dir == tmp_path / "docs" / "architecture"

    def test_design_dir_preserved(self, tmp_path):
        """design_dir default remains docs/design (unchanged from before)."""
        proj = Project(tmp_path)
        assert proj.design_dir == tmp_path / "docs" / "design"

    def test_default_paths_no_config_log(self, tmp_path):
        """log_dir returns .clasi/log by default."""
        proj = Project(tmp_path)
        assert proj.log_dir == tmp_path / ".clasi" / "log"

    def test_db_path_default(self, tmp_path):
        """db_path returns .clasi/.clasi.db by default."""
        proj = Project(tmp_path)
        assert proj.db_path == tmp_path / ".clasi" / ".clasi.db"

    def test_default_paths_empty_paths_key(self, tmp_path):
        """Config with process: se but no paths: key still returns defaults."""
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("process: se\n", encoding="utf-8")
        proj = Project(tmp_path)
        assert proj.issues_dir == tmp_path / "clasi" / "issues"
        assert proj.sprints_dir == tmp_path / "clasi" / "sprints"


# ---------------------------------------------------------------------------
# Config overrides
# ---------------------------------------------------------------------------


class TestConfigOverrides:
    """Test that paths: overrides in config.yaml are honored."""

    def _write_config(self, tmp_path: Path, content: str) -> None:
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "config.yaml").write_text(content, encoding="utf-8")

    def test_override_issues(self, tmp_path):
        """Custom issues path is returned; sprints still returns default."""
        self._write_config(
            tmp_path,
            "process: se\npaths:\n  issues: myteam/issues\n",
        )
        proj = Project(tmp_path)
        assert proj.issues_dir == tmp_path / "myteam" / "issues"
        assert proj.sprints_dir == tmp_path / "clasi" / "sprints"

    def test_override_sprints(self, tmp_path):
        """Custom sprints path is returned."""
        self._write_config(tmp_path, "paths:\n  sprints: custom/sprints\n")
        proj = Project(tmp_path)
        assert proj.sprints_dir == tmp_path / "custom" / "sprints"

    def test_override_architecture(self, tmp_path):
        """Custom architecture path is returned."""
        self._write_config(tmp_path, "paths:\n  architecture: .clasi/architecture\n")
        proj = Project(tmp_path)
        assert proj.architecture_dir == tmp_path / ".clasi" / "architecture"

    def test_override_db(self, tmp_path):
        """Custom db path is returned by db_path."""
        self._write_config(tmp_path, "paths:\n  db: custom/.mydb\n")
        proj = Project(tmp_path)
        assert proj.db_path == tmp_path / "custom" / ".mydb"

    def test_full_pin_config(self, tmp_path):
        """Full backward-compat pin config resolves all paths to .clasi/."""
        pin_yaml = (
            "process: se\n"
            "paths:\n"
            "  issues: .clasi/issues\n"
            "  sprints: .clasi/sprints\n"
            "  reflections: .clasi/reflections\n"
            "  architecture: .clasi/architecture\n"
            "  design: docs/design\n"
            "  logs: .clasi/log\n"
            "  db: .clasi/.clasi.db\n"
        )
        self._write_config(tmp_path, pin_yaml)
        proj = Project(tmp_path)
        assert proj.issues_dir == tmp_path / ".clasi" / "issues"
        assert proj.sprints_dir == tmp_path / ".clasi" / "sprints"
        assert proj.reflections_dir == tmp_path / ".clasi" / "reflections"
        assert proj.architecture_dir == tmp_path / ".clasi" / "architecture"
        assert proj.design_dir == tmp_path / "docs" / "design"
        assert proj.log_dir == tmp_path / ".clasi" / "log"
        assert proj.db_path == tmp_path / ".clasi" / ".clasi.db"


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Test that malformed or wrong-type configs fall back to defaults silently."""

    def test_malformed_yaml(self, tmp_path):
        """Corrupt config.yaml: properties return defaults, no exception."""
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "---bad\nmalformed: [yaml\n", encoding="utf-8"
        )
        proj = Project(tmp_path)
        assert proj.issues_dir == tmp_path / "clasi" / "issues"
        assert proj.sprints_dir == tmp_path / "clasi" / "sprints"

    def test_wrong_type_paths(self, tmp_path):
        """paths: "string" falls back silently to defaults."""
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "paths: just-a-string\n", encoding="utf-8"
        )
        proj = Project(tmp_path)
        assert proj.issues_dir == tmp_path / "clasi" / "issues"


# ---------------------------------------------------------------------------
# Lazy cache
# ---------------------------------------------------------------------------


class TestLazyCache:
    """Test that _path_config() loads config exactly once."""

    def test_lazy_cache(self, tmp_path):
        """_load_paths_config is called once even when multiple props are read."""
        proj = Project(tmp_path)
        call_count = 0
        original = _load_paths_config

        def counting_loader(root: Path) -> dict:
            nonlocal call_count
            call_count += 1
            return original(root)

        with patch("clasi.project._load_paths_config", side_effect=counting_loader):
            # Reset cached state so the patch is used
            proj._paths = None
            _ = proj.issues_dir
            _ = proj.issues_dir
            _ = proj.sprints_dir

        assert call_count == 1, f"Expected 1 call, got {call_count}"


# ---------------------------------------------------------------------------
# reflections_dir and db_path as new properties
# ---------------------------------------------------------------------------


class TestNewProperties:
    """Test new properties added by this ticket."""

    def test_reflections_dir_default(self, tmp_path):
        """reflections_dir property exists and returns clasi/reflections."""
        proj = Project(tmp_path)
        assert proj.reflections_dir == tmp_path / "clasi" / "reflections"

    def test_db_path_is_path_instance(self, tmp_path):
        """db_path returns a Path object."""
        proj = Project(tmp_path)
        assert isinstance(proj.db_path, Path)

    def test_db_uses_db_path(self, tmp_path):
        """db property uses self.db_path, not a hardcoded inline path."""
        proj = Project(tmp_path)
        # With default config, db_path == .clasi/.clasi.db
        proj.clasi_dir.mkdir(parents=True, exist_ok=True)
        db = proj.db
        assert db.path == proj.db_path

    def test_db_path_override_honored_by_db_property(self, tmp_path):
        """When db is overridden in config, the db property uses that path."""
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        custom_db_dir = tmp_path / "custom"
        custom_db_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "paths:\n  db: custom/.mydb\n", encoding="utf-8"
        )
        proj = Project(tmp_path)
        assert proj.db_path == tmp_path / "custom" / ".mydb"
        db = proj.db
        assert db.path == tmp_path / "custom" / ".mydb"


# ---------------------------------------------------------------------------
# clasi_dir is unchanged
# ---------------------------------------------------------------------------


class TestClasiDirUnchanged:
    """clasi_dir must remain .clasi/ regardless of config."""

    def test_clasi_dir_not_configurable(self, tmp_path):
        """clasi_dir always returns .clasi/ regardless of any config."""
        config_dir = tmp_path / ".clasi"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "paths:\n  issues: elsewhere/issues\n", encoding="utf-8"
        )
        proj = Project(tmp_path)
        assert proj.clasi_dir == tmp_path / ".clasi"


# ---------------------------------------------------------------------------
# ARTIFACT_PATH_DEFAULTS sanity check
# ---------------------------------------------------------------------------


class TestArtifactPathDefaults:
    """Verify the module-level constant has all required keys and values."""

    def test_all_required_keys_present(self):
        required = {"issues", "sprints", "reflections", "architecture", "design", "logs", "db"}
        assert required == set(ARTIFACT_PATH_DEFAULTS.keys())

    def test_default_values(self):
        assert ARTIFACT_PATH_DEFAULTS["issues"] == "clasi/issues"
        assert ARTIFACT_PATH_DEFAULTS["sprints"] == "clasi/sprints"
        assert ARTIFACT_PATH_DEFAULTS["reflections"] == "clasi/reflections"
        assert ARTIFACT_PATH_DEFAULTS["architecture"] == "docs/architecture"
        assert ARTIFACT_PATH_DEFAULTS["design"] == "docs/design"
        assert ARTIFACT_PATH_DEFAULTS["logs"] == ".clasi/log"
        assert ARTIFACT_PATH_DEFAULTS["db"] == ".clasi/.clasi.db"
