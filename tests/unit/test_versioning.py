"""Unit tests for clasi.versioning module."""

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from clasi.versioning import (
    DEFAULT_FORMAT,
    DEFAULT_TRIGGER,
    VERSION_PATTERN,
    build_tag_regex,
    build_version,
    compute_next_version,
    create_version_tag,
    detect_version_file,
    format_has_auto,
    load_version_format,
    load_version_trigger,
    parse_format,
    should_version,
    update_package_json_version,
    update_pyproject_version,
    update_version_file,
)


def _mock_today(year, month, day):
    """Create a mock date.today() that returns a proper date object."""
    real_date = date(year, month, day)
    mock_date = MagicMock()
    mock_date.today.return_value = real_date
    return mock_date


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


class TestParseFormat:
    def test_default_format(self):
        tokens = parse_format("X+.YYYYMMDD.R+")
        kinds = [k for k, _, _ in tokens]
        assert kinds == ["manual", "dot", "year", "month", "day", "dot", "rev"]

    def test_single_digit_tokens(self):
        tokens = parse_format("X.X.X")
        for kind, width, zpad in tokens:
            if kind == "manual":
                assert width == 1
                assert zpad is False

    def test_variable_width_manual(self):
        tokens = parse_format("X+.X+.X+")
        for kind, width, zpad in tokens:
            if kind == "manual":
                assert width == 0  # 0 = variable
                assert zpad is False

    def test_exact_two_digit(self):
        tokens = parse_format("XX.YYYYMMDD.R+")
        kind, width, zpad = tokens[0]
        assert kind == "manual"
        assert width == 2
        assert zpad is False

    def test_zero_padded_manual(self):
        tokens = parse_format("0XX.YYYYMMDD.R+")
        kind, width, zpad = tokens[0]
        assert kind == "manual"
        assert width == 2
        assert zpad is True

    def test_zero_padded_rev(self):
        tokens = parse_format("X+.YYYYMMDD.0RRR")
        kind, width, zpad = tokens[-1]
        assert kind == "rev"
        assert width == 3
        assert zpad is True

    def test_single_digit_rev(self):
        tokens = parse_format("X+.YYYYMMDD.R")
        kind, width, zpad = tokens[-1]
        assert kind == "rev"
        assert width == 1
        assert zpad is False

    def test_variable_rev(self):
        tokens = parse_format("X+.YYYYMMDD.R+")
        kind, width, zpad = tokens[-1]
        assert kind == "rev"
        assert width == 0
        assert zpad is False

    def test_invalid_format_rejected(self):
        with pytest.raises(ValueError, match="unrecognized"):
            parse_format("X+.YYYYMMDD.Z")


class TestFormatHasAuto:
    def test_default_is_auto(self):
        assert format_has_auto(parse_format("X+.YYYYMMDD.R+")) is True

    def test_semver_is_not_auto(self):
        assert format_has_auto(parse_format("X.X.X")) is False

    def test_date_only_is_auto(self):
        assert format_has_auto(parse_format("X+.YYYYMMDD")) is True


class TestBuildVersion:
    def test_default_format(self):
        parsed = parse_format("X+.YYYYMMDD.R+")
        result = build_version(parsed, [0], rev=3, today=date(2026, 3, 19))
        assert result == "0.20260319.3"

    def test_single_digit_semver(self):
        parsed = parse_format("X.X.X")
        result = build_version(parsed, [1, 2, 3])
        assert result == "1.2.3"

    def test_variable_width_semver(self):
        parsed = parse_format("X+.X+.X+")
        result = build_version(parsed, [1, 22, 333])
        assert result == "1.22.333"

    def test_zero_padded_major(self):
        parsed = parse_format("0XX.YYYYMMDD.R+")
        result = build_version(parsed, [1], rev=5, today=date(2026, 3, 19))
        assert result == "01.20260319.5"

    def test_zero_padded_rev(self):
        parsed = parse_format("X+.YYYYMMDD.0RRR")
        result = build_version(parsed, [0], rev=7, today=date(2026, 3, 19))
        assert result == "0.20260319.007"

    def test_missing_manual_defaults_to_zero(self):
        parsed = parse_format("X+.X+.X+")
        result = build_version(parsed, [1])
        assert result == "1.0.0"


class TestBuildTagRegex:
    def test_default_format_matches(self):
        pattern = build_tag_regex(parse_format("X+.YYYYMMDD.R+"))
        m = pattern.match("0.20260319.3")
        assert m is not None
        assert m.group("manual_0") == "0"
        assert m.group("year") == "2026"
        assert m.group("rev") == "3"

    def test_default_format_matches_multi_digit(self):
        pattern = build_tag_regex(parse_format("X+.YYYYMMDD.R+"))
        m = pattern.match("12.20260319.345")
        assert m is not None
        assert m.group("manual_0") == "12"
        assert m.group("rev") == "345"

    def test_single_digit_format_rejects_multi(self):
        pattern = build_tag_regex(parse_format("X.YYYYMMDD.R"))
        assert pattern.match("12.20260319.3") is None  # 12 is two digits
        assert pattern.match("1.20260319.3") is not None

    def test_exact_width_format(self):
        pattern = build_tag_regex(parse_format("XX.YYYYMMDD.RR"))
        assert pattern.match("01.20260319.03") is not None
        assert pattern.match("1.20260319.3") is None  # too few digits

    def test_semver_format(self):
        pattern = build_tag_regex(parse_format("X+.X+.X+"))
        m = pattern.match("1.22.333")
        assert m is not None
        assert m.group("manual_0") == "1"
        assert m.group("manual_1") == "22"
        assert m.group("manual_2") == "333"

    def test_v_prefix(self):
        pattern = build_tag_regex(parse_format("X+.YYYYMMDD.R+"))
        m = pattern.match("v0.20260319.1")
        assert m is not None


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


class TestComputeNextVersion:
    @patch("clasi.versioning.load_version_format", return_value="X+.YYYYMMDD.R+")
    @patch("clasi.versioning._get_existing_tags")
    @patch("clasi.versioning.date", _mock_today(2026, 2, 10))
    def test_first_version_of_day(self, mock_tags, _mock_fmt):
        mock_tags.return_value = []
        assert compute_next_version() == "0.20260210.1"

    @patch("clasi.versioning.load_version_format", return_value="X+.YYYYMMDD.R+")
    @patch("clasi.versioning._get_existing_tags")
    @patch("clasi.versioning.date", _mock_today(2026, 2, 10))
    def test_increments_build(self, mock_tags, _mock_fmt):
        mock_tags.return_value = ["v0.20260210.1", "v0.20260210.2"]
        assert compute_next_version() == "0.20260210.3"

    @patch("clasi.versioning.load_version_format", return_value="X+.YYYYMMDD.R+")
    @patch("clasi.versioning._get_existing_tags")
    @patch("clasi.versioning.date", _mock_today(2026, 2, 11))
    def test_resets_on_new_date(self, mock_tags, _mock_fmt):
        mock_tags.return_value = ["v0.20260210.5"]
        assert compute_next_version() == "0.20260211.1"

    @patch("clasi.versioning.load_version_format", return_value="X+.YYYYMMDD.R+")
    @patch("clasi.versioning._get_existing_tags")
    @patch("clasi.versioning.date", _mock_today(2026, 2, 10))
    def test_respects_major(self, mock_tags, _mock_fmt):
        mock_tags.return_value = ["v0.20260210.3", "v1.20260210.1"]
        assert compute_next_version(major=1) == "1.20260210.2"

    @patch("clasi.versioning.load_version_format", return_value="X+.YYYYMMDD.R+")
    @patch("clasi.versioning._get_existing_tags")
    @patch("clasi.versioning.date", _mock_today(2026, 2, 10))
    def test_ignores_non_matching_tags(self, mock_tags, _mock_fmt):
        mock_tags.return_value = ["release-1.0", "v0.2.0", "v0.20260210.1"]
        assert compute_next_version() == "0.20260210.2"

    @patch("clasi.versioning.load_version_format", return_value="X+.YYYYMMDD.0RRR")
    @patch("clasi.versioning._get_existing_tags")
    @patch("clasi.versioning.date", _mock_today(2026, 3, 19))
    def test_zero_padded_rev(self, mock_tags, _mock_fmt):
        mock_tags.return_value = ["v0.20260319.002"]
        assert compute_next_version() == "0.20260319.003"

    @patch("clasi.versioning.load_version_format", return_value="X+.X+.X+")
    @patch("clasi.versioning._get_existing_tags")
    def test_fully_manual_format(self, mock_tags, _mock_fmt):
        mock_tags.return_value = []
        result = compute_next_version(major=1)
        assert result == "1.0.0"

    @patch("clasi.versioning.load_version_format", return_value="X+.YYYYMMDD.R+")
    @patch("clasi.versioning.read_current_version", return_value="0.20260210.4")
    @patch("clasi.versioning._get_existing_tags")
    @patch("clasi.versioning.date", _mock_today(2026, 2, 10))
    def test_advances_past_current_version_when_no_tag(
        self, mock_tags, _mock_current, _mock_fmt
    ):
        # Simulates two consecutive `clasi version bump` (no --tag) calls:
        # the first wrote 0.20260210.4 to pyproject.toml but created no tag,
        # so without reading the file we would recompute 0.20260210.4 again.
        mock_tags.return_value = []
        assert compute_next_version() == "0.20260210.5"


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


class TestUpdatePyprojectVersion:
    def test_updates_version(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.2.0"\n')

        update_pyproject_version("0.20260210.1", pyproject)

        content = pyproject.read_text()
        assert 'version = "0.20260210.1"' in content
        assert 'name = "test"' in content

    def test_raises_on_missing_version(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\n')

        with pytest.raises(ValueError, match="Could not find version"):
            update_pyproject_version("0.20260210.1", pyproject)

    def test_noop_when_version_already_matches(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.20260210.1"\n')

        update_pyproject_version("0.20260210.1", pyproject)

        assert 'version = "0.20260210.1"' in pyproject.read_text()


class TestUpdatePackageJsonVersion:
    def test_updates_version(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"name": "test", "version": "1.0.0"}, indent=2) + "\n")

        update_package_json_version("0.20260210.1", pkg)

        data = json.loads(pkg.read_text())
        assert data["version"] == "0.20260210.1"
        assert data["name"] == "test"

    def test_preserves_indent(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"name": "test", "version": "1.0.0"}, indent=2) + "\n")

        update_package_json_version("0.20260210.1", pkg)

        content = pkg.read_text()
        assert "  " in content  # indent preserved

    def test_raises_on_no_version_field(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"name": "test-private"}, indent=2) + "\n")

        with pytest.raises(ValueError, match="No 'version' field"):
            update_package_json_version("0.20260210.1", pkg)


class TestUpdateVersionFile:
    def test_dispatches_to_pyproject(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"\n')

        update_version_file(pyproject, "pyproject", "0.20260210.1")

        assert 'version = "0.20260210.1"' in pyproject.read_text()

    def test_dispatches_to_package_json(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"name": "test", "version": "1.0.0"}, indent=2) + "\n")

        update_version_file(pkg, "package_json", "0.20260210.1")

        data = json.loads(pkg.read_text())
        assert data["version"] == "0.20260210.1"

    def test_raises_on_unknown_type(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown version file type"):
            update_version_file(tmp_path / "Cargo.toml", "cargo", "0.1.0")


class TestCreateVersionTag:
    @patch("clasi.versioning.subprocess")
    def test_creates_tag(self, mock_subprocess):
        mock_subprocess.run.return_value.returncode = 0

        create_version_tag("0.20260210.1")

        mock_subprocess.run.assert_called_once_with(
            ["git", "tag", "v0.20260210.1"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("clasi.versioning.subprocess")
    def test_raises_on_failure(self, mock_subprocess):
        mock_subprocess.run.return_value.returncode = 1
        mock_subprocess.run.return_value.stderr = "tag already exists"

        with pytest.raises(RuntimeError, match="Failed to create tag"):
            create_version_tag("0.20260210.1")


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
