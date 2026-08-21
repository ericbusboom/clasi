"""
tests/unit/test_platform_manifest.py

Unit tests for clasi.platforms._manifest — the single-tenant install
manifest read/write/delete leaf module (sprint 033, ticket 001, fix A).

Covers:
- manifest_path() naming.
- write/read round-trip.
- read on a missing manifest returns None.
- read on a corrupt manifest raises (callers decide how to treat that).
- write is atomic: no leftover .tmp file, and an existing manifest is
  fully replaced, not merged.
- delete_manifest()'s True/False return for present/absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from clasi.platforms import _manifest


# ---------------------------------------------------------------------------
# manifest_path
# ---------------------------------------------------------------------------


class TestManifestPath:
    def test_path_is_dot_clasi_manifest_json_under_platform_dir(
        self, tmp_path: Path
    ) -> None:
        platform_dir = tmp_path / ".claude"
        assert (
            _manifest.manifest_path(platform_dir)
            == platform_dir / ".clasi-manifest.json"
        )


# ---------------------------------------------------------------------------
# read_manifest
# ---------------------------------------------------------------------------


class TestReadManifest:
    def test_read_missing_file_returns_none(self, tmp_path: Path) -> None:
        platform_dir = tmp_path / ".claude"
        assert _manifest.read_manifest(platform_dir) is None

    def test_read_missing_platform_dir_returns_none(self, tmp_path: Path) -> None:
        """The platform directory itself need not exist yet."""
        platform_dir = tmp_path / "does-not-exist" / ".claude"
        assert _manifest.read_manifest(platform_dir) is None

    def test_read_corrupt_json_raises(self, tmp_path: Path) -> None:
        """A malformed manifest is not swallowed by this module — the
        caller (clasi.platforms.claude) decides whether corrupt JSON
        should be treated as "no manifest"."""
        platform_dir = tmp_path / ".claude"
        platform_dir.mkdir(parents=True)
        (platform_dir / ".clasi-manifest.json").write_text(
            "{not valid json", encoding="utf-8"
        )
        with pytest.raises(json.JSONDecodeError):
            _manifest.read_manifest(platform_dir)


# ---------------------------------------------------------------------------
# write_manifest
# ---------------------------------------------------------------------------


class TestWriteManifest:
    def test_write_creates_platform_dir_if_missing(self, tmp_path: Path) -> None:
        platform_dir = tmp_path / ".claude"
        assert not platform_dir.exists()
        _manifest.write_manifest(platform_dir, {"version": 1, "entries": []})
        assert platform_dir.is_dir()

    def test_write_then_read_round_trips(self, tmp_path: Path) -> None:
        platform_dir = tmp_path / ".claude"
        data = {
            "version": 1,
            "entries": [
                {"path": ".claude/rules/mcp-required.md", "kind": "rule-file"},
                {"path": "CLAUDE.md", "kind": "marker-block"},
            ],
        }
        _manifest.write_manifest(platform_dir, data)
        assert _manifest.read_manifest(platform_dir) == data

    def test_write_leaves_no_tmp_file(self, tmp_path: Path) -> None:
        """Atomicity: the tmp sibling used during the write is gone
        afterward (write-to-.tmp, then os.replace over the final path)."""
        platform_dir = tmp_path / ".claude"
        _manifest.write_manifest(platform_dir, {"version": 1, "entries": []})
        tmp_sibling = _manifest.manifest_path(platform_dir).with_suffix(".tmp")
        assert not tmp_sibling.exists()

    def test_write_replaces_not_merges(self, tmp_path: Path) -> None:
        """A second write fully replaces the first — no merging of entries."""
        platform_dir = tmp_path / ".claude"
        _manifest.write_manifest(
            platform_dir,
            {"version": 1, "entries": [{"path": "a", "kind": "rule-file"}]},
        )
        _manifest.write_manifest(
            platform_dir,
            {"version": 1, "entries": [{"path": "b", "kind": "rule-file"}]},
        )
        data = _manifest.read_manifest(platform_dir)
        assert data["entries"] == [{"path": "b", "kind": "rule-file"}]


# ---------------------------------------------------------------------------
# delete_manifest
# ---------------------------------------------------------------------------


class TestDeleteManifest:
    def test_delete_existing_returns_true_and_removes_file(
        self, tmp_path: Path
    ) -> None:
        platform_dir = tmp_path / ".claude"
        _manifest.write_manifest(platform_dir, {"version": 1, "entries": []})
        assert _manifest.delete_manifest(platform_dir) is True
        assert not _manifest.manifest_path(platform_dir).exists()

    def test_delete_missing_returns_false(self, tmp_path: Path) -> None:
        platform_dir = tmp_path / ".claude"
        assert _manifest.delete_manifest(platform_dir) is False
