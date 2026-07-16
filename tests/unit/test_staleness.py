"""Unit tests for clasi.staleness.

Covers both detection signals against real importlib.metadata /
source_path shapes (no synthetic stand-ins per house standard):

1. In-process drift: cached __version__ vs a live importlib.metadata.version()
   lookup, using the actual installed "clasi" distribution.
2. Dogfooding drift: a project root that looks like the CLASI source repo
   (real pyproject.toml + src/clasi/__init__.py on disk) whose declared
   version and editable-source path do or do not match the running
   process's real metadata_version / source_path.

Every "stale" test has a matching "not stale" counterpart proving the
signal does not fire when reverted to a consistent state (the revert-check
house standard from sprint 019).
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
from pathlib import Path

from clasi.staleness import (
    _is_clasi_source_repo,
    _read_repo_clasi_version,
    check_staleness,
)


def _real_metadata_version() -> str:
    return importlib.metadata.version("clasi")


def _real_source_path() -> str:
    spec = importlib.util.find_spec("clasi")
    return str(spec.origin) if spec and spec.origin else "unknown"


def _write_clasi_repo_skeleton(root: Path, version: str) -> None:
    """Write a minimal but real pyproject.toml + src/clasi/__init__.py
    matching the actual CLASI repo's structure, so _is_clasi_source_repo
    and _read_repo_clasi_version exercise real file parsing."""
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "clasi"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    src_clasi = root / "src" / "clasi"
    src_clasi.mkdir(parents=True, exist_ok=True)
    (src_clasi / "__init__.py").write_text('"""CLASI."""\n', encoding="utf-8")


# ---------------------------------------------------------------------------
# Signal 1: in-process drift (cached __version__ vs live metadata_version)
# ---------------------------------------------------------------------------


class TestInProcessDriftSignal:
    def test_matching_version_is_not_stale(self, tmp_path):
        """Cached version equal to the real live metadata_version: not stale."""
        real_version = _real_metadata_version()
        report = check_staleness(tmp_path, real_version)
        assert report.stale is False
        assert report.reasons == []

    def test_mismatched_version_is_stale(self, tmp_path):
        """Cached version deliberately behind the real live metadata_version.

        Revert-check: reverting to the matching version (above) makes this
        pass — proving the signal is actually exercised, not vacuously true.
        """
        real_version = _real_metadata_version()
        stale_cached_version = "0.19990101.1"  # guaranteed behind any real version
        assert stale_cached_version != real_version

        report = check_staleness(tmp_path, stale_cached_version)
        assert report.stale is True
        assert any("differs from the live installed package version" in r for r in report.reasons)
        assert stale_cached_version in report.warning()
        assert real_version in report.warning()

    def test_unknown_running_version_does_not_false_positive(self, tmp_path):
        """The '0.0.0-unknown' sentinel (import-time failure) must not be
        reported as drift — there is nothing meaningful to compare."""
        report = check_staleness(tmp_path, "0.0.0-unknown")
        assert not any(
            "differs from the live installed package version" in r
            for r in report.reasons
        )


# ---------------------------------------------------------------------------
# Signal 2: dogfooding drift (project root looks like the CLASI repo itself)
# ---------------------------------------------------------------------------


class TestIsClasiSourceRepo:
    def test_real_structure_is_detected(self, tmp_path):
        _write_clasi_repo_skeleton(tmp_path, "0.20260715.4")
        assert _is_clasi_source_repo(tmp_path) is True

    def test_missing_src_clasi_is_not_detected(self, tmp_path):
        """A pyproject.toml with name='clasi' but no src/clasi/__init__.py
        (e.g. a consumer project that happens to be named 'clasi') is not
        treated as the source repo."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "clasi"\nversion = "1.0.0"\n', encoding="utf-8"
        )
        assert _is_clasi_source_repo(tmp_path) is False

    def test_ordinary_consumer_project_is_not_detected(self, tmp_path):
        """A normal consumer project (different package name) never
        satisfies the dogfooding-drift precondition."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "some-other-app"\nversion = "1.0.0"\n',
            encoding="utf-8",
        )
        src = tmp_path / "src" / "some_other_app"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("", encoding="utf-8")
        assert _is_clasi_source_repo(tmp_path) is False

    def test_no_pyproject_is_not_detected(self, tmp_path):
        assert _is_clasi_source_repo(tmp_path) is False


class TestReadRepoClasiVersion:
    def test_reads_real_version_string(self, tmp_path):
        _write_clasi_repo_skeleton(tmp_path, "0.20260715.4")
        assert _read_repo_clasi_version(tmp_path) == "0.20260715.4"

    def test_missing_pyproject_returns_none(self, tmp_path):
        assert _read_repo_clasi_version(tmp_path) is None

    def test_reads_this_repos_own_actual_pyproject(self):
        """Sanity check against the real repo on disk (not a fixture)."""
        repo_root = Path(__file__).resolve().parents[2]
        version = _read_repo_clasi_version(repo_root)
        assert version is not None
        assert version[0].isdigit()


class TestDogfoodingDriftSignal:
    def test_matching_repo_version_and_source_path_is_not_stale(self, tmp_path):
        """A CLASI-repo-shaped project whose declared version and editable
        source path both match the running process: not stale.

        Uses a real symlink from the skeleton's src/clasi/__init__.py to
        the actual running module's real __init__.py, so the source_path
        comparison is a genuine match rather than an assumed one — this
        is the only way to make the source_path signal deterministically
        agree without faking check_staleness's internals.
        """
        real_version = _real_metadata_version()
        real_source = Path(_real_source_path())

        src_clasi = tmp_path / "src" / "clasi"
        src_clasi.mkdir(parents=True)
        (tmp_path / "pyproject.toml").write_text(
            f'[project]\nname = "clasi"\nversion = "{real_version}"\n',
            encoding="utf-8",
        )
        (src_clasi / "__init__.py").symlink_to(real_source)

        report = check_staleness(tmp_path, real_version)

        assert not any(
            "does not match this repo's editable source" in r
            for r in report.reasons
        )
        assert not any(
            "is not running this working tree's code" in r
            for r in report.reasons
        )
        assert report.stale is False

    def test_mismatched_repo_version_is_stale(self, tmp_path):
        """Repo pyproject.toml declares a newer version than the running
        process reports: dogfooding-drift signal fires.

        Revert-check: setting the repo version to match the real live
        metadata_version (test above) makes this stop firing.
        """
        real_version = _real_metadata_version()
        newer_fake_version = "0.99990101.1"
        assert newer_fake_version != real_version
        _write_clasi_repo_skeleton(tmp_path, newer_fake_version)

        report = check_staleness(tmp_path, real_version)
        assert report.stale is True
        assert any(
            "is not running this working tree's code" in r
            or "does not match this repo's editable source" in r
            for r in report.reasons
        )
        assert newer_fake_version in report.warning()

    def test_consumer_project_never_triggers_dogfooding_signal(self, tmp_path):
        """A project that merely depends on clasi (not the clasi repo
        itself) must never see the dogfooding-drift signal, regardless of
        what its own pyproject.toml version says — the whole point of
        gating on _is_clasi_source_repo."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "some-consumer-app"\nversion = "0.0.1"\n',
            encoding="utf-8",
        )
        real_version = _real_metadata_version()
        report = check_staleness(tmp_path, real_version)
        assert report.repo_version is None
        assert not any(
            "editable source" in r or "working tree's code" in r
            for r in report.reasons
        )

    def test_never_raises_on_unreadable_project_root(self, tmp_path):
        """A nonexistent project root must not raise — check_staleness is
        called from hook/server startup paths that must never crash."""
        missing = tmp_path / "does-not-exist"
        report = check_staleness(missing, "0.0.0-unknown")
        assert report.stale in (True, False)  # just must not raise
