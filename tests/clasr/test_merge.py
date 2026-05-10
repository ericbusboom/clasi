"""
tests/clasr/test_merge.py

Tests for clasr.merge — JSON deep-merge for multi-provider passthrough.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from clasr.merge import is_json_passthrough, merge_json_files, reverse_diff


# ---------------------------------------------------------------------------
# is_json_passthrough
# ---------------------------------------------------------------------------


def test_is_json_passthrough_true():
    assert is_json_passthrough(Path("settings.json")) is True


def test_is_json_passthrough_false_md():
    assert is_json_passthrough(Path("README.md")) is False


def test_is_json_passthrough_false_toml():
    assert is_json_passthrough(Path("pyproject.toml")) is False


def test_is_json_passthrough_false_txt():
    assert is_json_passthrough(Path("notes.txt")) is False


# ---------------------------------------------------------------------------
# merge_json_files — basic / no conflict
# ---------------------------------------------------------------------------


def test_merge_json_files_missing_existing_raises(tmp_path):
    """FileNotFoundError when existing path does not exist."""
    missing = tmp_path / "nonexistent.json"
    with pytest.raises(FileNotFoundError):
        merge_json_files(missing, {"key": "val"}, "providerA", "providerB")


def test_merge_json_files_basic(tmp_path):
    """No conflicts: merged dict has all keys; diff is a dict with incoming keys."""
    existing = tmp_path / "settings.json"
    existing.write_text(json.dumps({"alpha": 1}))

    incoming = {"beta": 2, "gamma": 3}
    merged, diff = merge_json_files(existing, incoming, "provA", "provB")

    assert merged == {"alpha": 1, "beta": 2, "gamma": 3}
    assert isinstance(diff, dict)
    assert "beta" in diff
    assert "gamma" in diff


def test_merge_json_files_returns_contributed_diff(tmp_path):
    """diff is a dict containing only what incoming contributes beyond existing."""
    existing = tmp_path / "s.json"
    existing.write_text(json.dumps({"existing_key": True}))

    incoming = {"mcpServers": {"my-server": {}}}
    _, diff = merge_json_files(existing, incoming, "provA", "provB")

    assert isinstance(diff, dict)
    assert "mcpServers" in diff


# ---------------------------------------------------------------------------
# merge_json_files — conflicts
# ---------------------------------------------------------------------------


def test_merge_json_files_conflict_warning(tmp_path, capsys):
    """A top-level key conflict emits a WARNING to stderr naming both providers."""
    existing = tmp_path / "settings.json"
    existing.write_text(json.dumps({"foo": "old"}))

    merge_json_files(existing, {"foo": "new"}, "providerNew", "providerOld")

    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "providerNew" in captured.err
    assert "providerOld" in captured.err
    assert "foo" in captured.err


def test_merge_json_files_conflict_incoming_wins(tmp_path):
    """On conflict at the top level the incoming (provider) value wins."""
    existing = tmp_path / "settings.json"
    existing.write_text(json.dumps({"foo": "old_value"}))

    merged, _ = merge_json_files(
        existing, {"foo": "new_value"}, "providerNew", "providerOld"
    )

    assert merged["foo"] == "new_value"


# ---------------------------------------------------------------------------
# merge_json_files — deep merge
# ---------------------------------------------------------------------------


def test_merge_json_files_deep_merge(tmp_path):
    """Nested dicts are merged recursively rather than replaced."""
    existing = tmp_path / "settings.json"
    existing.write_text(json.dumps({"servers": {"a": 1}}))

    merged, _ = merge_json_files(
        existing, {"servers": {"b": 2}}, "provA", "provB"
    )

    assert merged == {"servers": {"a": 1, "b": 2}}


def test_merge_json_files_non_dict_deeper_level_incoming_wins(tmp_path):
    """When base value is not a dict but overlay is (or vice-versa), overlay wins."""
    existing = tmp_path / "settings.json"
    existing.write_text(json.dumps({"key": "scalar"}))

    merged, _ = merge_json_files(
        existing, {"key": {"nested": True}}, "provA", "provB"
    )

    assert merged["key"] == {"nested": True}


def test_merge_json_files_diff_excludes_unchanged_keys(tmp_path):
    """Diff omits incoming keys whose value matches what is already in existing."""
    existing = tmp_path / "settings.json"
    existing.write_text(json.dumps({"shared": "same-value", "other": 1}))

    incoming = {"shared": "same-value", "new_key": 42}
    _, diff = merge_json_files(existing, incoming, "provA", "provB")

    assert "shared" not in diff
    assert "new_key" in diff


# ---------------------------------------------------------------------------
# reverse_diff
# ---------------------------------------------------------------------------


def test_reverse_diff_removes_contributed_keys(tmp_path):
    """reverse_diff strips exactly the keys recorded in the diff."""
    existing = tmp_path / "settings.json"
    existing.write_text(json.dumps({"alpha": 1}))

    incoming = {"beta": 2, "gamma": 3}
    merged, diff = merge_json_files(existing, incoming, "provA", "provB")

    restored = reverse_diff(merged, diff)
    assert restored == {"alpha": 1}


def test_reverse_diff_nested(tmp_path):
    """reverse_diff removes only contributed nested keys, not pre-existing siblings."""
    existing = tmp_path / "settings.json"
    existing.write_text(json.dumps({"servers": {"a": 1}}))

    incoming = {"servers": {"b": 2}}
    merged, diff = merge_json_files(existing, incoming, "provA", "provB")

    restored = reverse_diff(merged, diff)
    assert restored == {"servers": {"a": 1}}


def test_reverse_diff_public_export():
    """reverse_diff is importable as a top-level public function."""
    current = {"x": 1, "y": 2}
    diff = {"y": 2}
    result = reverse_diff(current, diff)
    assert result == {"x": 1}
