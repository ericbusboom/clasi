"""Unit tests for clasi.versioning module.

Tests cover only the clasi-specific shim:
  - VERSION_PATTERN compat alias
  - load_version_format (reads .clasi/settings.yaml)
  - load_version_trigger (reads .clasi/settings.yaml)
  - should_version
  - detect_version_file

Logic for parse_format, build_version, build_tag_regex, update_*_version,
update_version_file, and create_version_tag now lives in dotconfig and is
tested in dotconfig's own suite.
"""

import pytest

from clasi.versioning import (
    DEFAULT_FORMAT,
    DEFAULT_TRIGGER,
    VERSION_PATTERN,
    detect_version_file,
    load_version_format,
    load_version_trigger,
    should_version,
)


class TestVersionPattern:
    """Legacy VERSION_PATTERN backward compat."""

    def test_matches_valid_version(self):
        assert VERSION_PATTERN.match("0.20260210.1")
        assert VERSION_PATTERN.match("1.20260210.42")

    def test_matches_with_v_prefix(self):
        assert VERSION_PATTERN.match("v0.20260210.1")

    def test_rejects_invalid(self):
        assert not VERSION_PATTERN.match("0.1.0")
        assert not VERSION_PATTERN.match("abc")
        assert not VERSION_PATTERN.match("0.2026021.1")  # 7 digits


class TestLoadVersionFormat:
    def test_returns_default_when_no_file(self, tmp_path):
        assert load_version_format(tmp_path) == DEFAULT_FORMAT

    def test_reads_from_settings(self, tmp_path):
        settings = tmp_path / "docs" / "clasi" / "settings.yaml"
        settings.parent.mkdir(parents=True)
        settings.write_text('version_format: "X+.X+.X+"\n')
        assert load_version_format(tmp_path) == "X+.X+.X+"

    def test_returns_default_on_missing_key(self, tmp_path):
        settings = tmp_path / "docs" / "clasi" / "settings.yaml"
        settings.parent.mkdir(parents=True)
        settings.write_text("other_key: value\n")
        assert load_version_format(tmp_path) == DEFAULT_FORMAT

    def test_returns_default_on_bad_yaml(self, tmp_path):
        settings = tmp_path / "docs" / "clasi" / "settings.yaml"
        settings.parent.mkdir(parents=True)
        settings.write_text("not: valid: yaml: {{{\n")
        assert load_version_format(tmp_path) == DEFAULT_FORMAT


class TestLoadVersionTrigger:
    def test_returns_default_when_no_file(self, tmp_path):
        assert load_version_trigger(tmp_path) == DEFAULT_TRIGGER

    def test_reads_every_sprint(self, tmp_path):
        settings = tmp_path / "docs" / "clasi" / "settings.yaml"
        settings.parent.mkdir(parents=True)
        settings.write_text('version_trigger: "every_sprint"\n')
        assert load_version_trigger(tmp_path) == "every_sprint"

    def test_reads_manual(self, tmp_path):
        settings = tmp_path / "docs" / "clasi" / "settings.yaml"
        settings.parent.mkdir(parents=True)
        settings.write_text('version_trigger: "manual"\n')
        assert load_version_trigger(tmp_path) == "manual"

    def test_invalid_value_returns_default(self, tmp_path):
        settings = tmp_path / "docs" / "clasi" / "settings.yaml"
        settings.parent.mkdir(parents=True)
        settings.write_text('version_trigger: "bogus"\n')
        assert load_version_trigger(tmp_path) == DEFAULT_TRIGGER


class TestShouldVersion:
    def test_manual_never_versions(self):
        assert should_version("manual", "sprint_close") is False
        assert should_version("manual", "change") is False

    def test_every_sprint_only_on_close(self):
        assert should_version("every_sprint", "sprint_close") is True
        assert should_version("every_sprint", "change") is False

    def test_every_change_always_versions(self):
        assert should_version("every_change", "sprint_close") is True
        assert should_version("every_change", "change") is True


class TestDetectVersionFile:
    def test_detect_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n')
        result = detect_version_file(tmp_path)
        assert result is not None
        assert result[0] == tmp_path / "pyproject.toml"
        assert result[1] == "pyproject"

    def test_detect_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test", "version": "1.0.0"}\n')
        result = detect_version_file(tmp_path)
        assert result is not None
        assert result[0] == tmp_path / "package.json"
        assert result[1] == "package_json"

    def test_pyproject_wins_when_both_exist(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n')
        (tmp_path / "package.json").write_text('{"name": "test", "version": "1.0.0"}\n')
        result = detect_version_file(tmp_path)
        assert result is not None
        assert result[1] == "pyproject"

    def test_returns_none_when_neither_exists(self, tmp_path):
        assert detect_version_file(tmp_path) is None
