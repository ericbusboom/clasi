"""Tests for clasi.migrate_command module."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from clasi.cli import cli
from clasi.migrate_command import (
    CANDIDATE_LOCATIONS,
    Move,
    _check_no_execution_lock,
    _is_git_repo,
    _is_tracked,
    _update_gitignore,
    detect_moves,
    execute_moves,
    run_migrate,
)
from clasi.project import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_docs_clasi(root: Path) -> Path:
    """Create a minimal docs/clasi/ structure inside *root* (legacy layout)."""
    docs_clasi = root / "docs" / "clasi"
    docs_clasi.mkdir(parents=True, exist_ok=True)
    (docs_clasi / "sprints").mkdir()
    (docs_clasi / "log").mkdir()
    (docs_clasi / "issues").mkdir()
    (docs_clasi / "architecture").mkdir()
    return docs_clasi


def _make_dot_clasi(root: Path) -> Path:
    """Create a minimal .clasi/ structure inside *root*."""
    dot_clasi = root / ".clasi"
    dot_clasi.mkdir(parents=True, exist_ok=True)
    (dot_clasi / "sprints").mkdir()
    (dot_clasi / "log").mkdir()
    (dot_clasi / "issues").mkdir()
    (dot_clasi / "architecture").mkdir()
    return dot_clasi


def _init_git_repo(root: Path) -> None:
    """Initialize a bare git repository at *root*."""
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )


def _make_project(root: Path, config_paths: dict | None = None) -> Project:
    """Create a Project pointing at *root*, optionally writing a config.yaml."""
    clasi_dir = root / ".clasi"
    clasi_dir.mkdir(parents=True, exist_ok=True)
    if config_paths is not None:
        import yaml
        config_file = clasi_dir / "config.yaml"
        config_file.write_text(
            yaml.dump({"process": "se", "paths": config_paths}), encoding="utf-8"
        )
    return Project(root)


# ---------------------------------------------------------------------------
# CANDIDATE_LOCATIONS sanity
# ---------------------------------------------------------------------------


class TestCandidateLocations:
    def test_all_default_keys_present(self):
        """Every ARTIFACT_PATH_DEFAULTS category has a migration source.

        "architecture" is the one exception: it remains a probed legacy
        source category (for old .clasi/architecture / docs/clasi/architecture
        content) but has no destination property of its own anymore — its
        destination now resolves to design_dir (see detect_moves'
        category_dst), so it is not in ARTIFACT_PATH_DEFAULTS.
        """
        from clasi.project import ARTIFACT_PATH_DEFAULTS

        assert set(ARTIFACT_PATH_DEFAULTS.keys()) <= set(CANDIDATE_LOCATIONS.keys())
        assert set(CANDIDATE_LOCATIONS.keys()) - set(ARTIFACT_PATH_DEFAULTS.keys()) == {
            "architecture"
        }

    def test_db_is_file_candidate(self):
        """db candidates should reference a .db filename, not a directory."""
        for rel in CANDIDATE_LOCATIONS["db"]:
            assert rel.endswith(".clasi.db"), rel


# ---------------------------------------------------------------------------
# Move dataclass
# ---------------------------------------------------------------------------


class TestMoveDataclass:
    def test_fields(self, tmp_path):
        src = tmp_path / "a"
        dst = tmp_path / "b"
        m = Move(category="issues", src=src, dst=dst, mode="move", is_file=False)
        assert m.category == "issues"
        assert m.src == src
        assert m.dst == dst
        assert m.mode == "move"
        assert m.is_file is False

    def test_is_file_true_for_db(self, tmp_path):
        src = tmp_path / ".clasi.db"
        dst = tmp_path / "other" / ".clasi.db"
        m = Move(category="db", src=src, dst=dst, mode="move", is_file=True)
        assert m.is_file is True


# ---------------------------------------------------------------------------
# _is_git_repo
# ---------------------------------------------------------------------------


class TestIsGitRepo:
    @pytest.mark.slow  # 032/008: real git repo (_init_git_repo)
    def test_returns_true_inside_git_repo(self, tmp_path):
        _init_git_repo(tmp_path)
        assert _is_git_repo(tmp_path) is True

    def test_returns_false_outside_git_repo(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        assert _is_git_repo(plain) is False


# ---------------------------------------------------------------------------
# _is_tracked
# ---------------------------------------------------------------------------


class TestIsTracked:
    @pytest.mark.slow  # 032/008: real git repo (_init_git_repo)
    def test_returns_true_for_tracked_file(self, tmp_path):
        _init_git_repo(tmp_path)
        f = tmp_path / "tracked.md"
        f.write_text("# x", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "tracked.md"],
            check=True,
            capture_output=True,
        )
        assert _is_tracked(f, tmp_path) is True

    @pytest.mark.slow  # 032/008: real git repo (_init_git_repo)
    def test_returns_false_for_untracked_file(self, tmp_path):
        _init_git_repo(tmp_path)
        f = tmp_path / "untracked.md"
        f.write_text("# x", encoding="utf-8")
        assert _is_tracked(f, tmp_path) is False


# ---------------------------------------------------------------------------
# _find_untracked_sources
# ---------------------------------------------------------------------------


class TestFindUntrackedSources:
    @pytest.mark.slow  # 032/008: real git repo (_init_git_repo)
    def test_reports_untracked_file_in_move(self, tmp_path):
        from clasi.migrate_command import _find_untracked_sources

        _init_git_repo(tmp_path)
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        untracked = src_dir / "issue.md"
        untracked.write_text("# x", encoding="utf-8")

        move = Move(
            category="issues",
            src=src_dir,
            dst=tmp_path / "clasi" / "issues",
            mode="move",
            is_file=False,
        )
        result = _find_untracked_sources([move], tmp_path)
        assert untracked in result

    @pytest.mark.slow  # 032/008: real git repo (_init_git_repo)
    def test_ignores_tracked_files(self, tmp_path):
        from clasi.migrate_command import _find_untracked_sources

        _init_git_repo(tmp_path)
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        f = src_dir / "issue.md"
        f.write_text("# x", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "-A"],
            check=True,
            capture_output=True,
        )

        move = Move(
            category="issues",
            src=src_dir,
            dst=tmp_path / "clasi" / "issues",
            mode="move",
            is_file=False,
        )
        assert _find_untracked_sources([move], tmp_path) == []

    @pytest.mark.slow  # 032/008: real git repo (_init_git_repo)
    def test_ignores_gitkeep_housekeeping(self, tmp_path):
        """.gitkeep is removed rather than moved, so it must not block init."""
        from clasi.migrate_command import _find_untracked_sources

        _init_git_repo(tmp_path)
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        (src_dir / ".gitkeep").write_text("", encoding="utf-8")

        move = Move(
            category="issues",
            src=src_dir,
            dst=tmp_path / "clasi" / "issues",
            mode="move",
            is_file=False,
        )
        assert _find_untracked_sources([move], tmp_path) == []


# ---------------------------------------------------------------------------
# _update_gitignore  (generalized)
# ---------------------------------------------------------------------------


class TestUpdateGitignore:
    def test_replaces_old_entry(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\ndocs/clasi/log/\nbuild/\n", encoding="utf-8")
        _update_gitignore(tmp_path, [("docs/clasi/log/", ".clasi/log/")])
        content = gitignore.read_text(encoding="utf-8")
        assert "docs/clasi/log/" not in content
        assert ".clasi/log/" in content
        assert "node_modules/" in content
        assert "build/" in content

    def test_no_op_when_gitignore_missing(self, tmp_path):
        _update_gitignore(tmp_path, [("docs/clasi/log/", ".clasi/log/")])
        assert not (tmp_path / ".gitignore").exists()

    def test_no_op_when_old_entry_absent(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        original = "node_modules/\nbuild/\n"
        gitignore.write_text(original, encoding="utf-8")
        _update_gitignore(tmp_path, [("docs/clasi/log/", ".clasi/log/")])
        assert gitignore.read_text(encoding="utf-8") == original

    def test_replaces_all_occurrences(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("docs/clasi/log/\ndocs/clasi/log/\n", encoding="utf-8")
        _update_gitignore(tmp_path, [("docs/clasi/log/", ".clasi/log/")])
        content = gitignore.read_text(encoding="utf-8")
        assert "docs/clasi/log/" not in content
        assert content.count(".clasi/log/") == 2

    def test_applies_multiple_replacements(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(
            "docs/clasi/log/\ndocs/clasi/issues/\nbuild/\n", encoding="utf-8"
        )
        _update_gitignore(
            tmp_path,
            [
                ("docs/clasi/log/", ".clasi/log/"),
                ("docs/clasi/issues/", ".clasi/issues/"),
            ],
        )
        content = gitignore.read_text(encoding="utf-8")
        assert ".clasi/log/" in content
        assert ".clasi/issues/" in content
        assert "docs/clasi/" not in content

    def test_empty_replacements_list_is_noop(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        original = "node_modules/\n"
        gitignore.write_text(original, encoding="utf-8")
        _update_gitignore(tmp_path, [])
        assert gitignore.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# _check_no_execution_lock  (generalized)
# ---------------------------------------------------------------------------


class TestCheckNoExecutionLock:
    def test_passes_when_no_db(self, tmp_path):
        _check_no_execution_lock(tmp_path)

    def test_passes_when_db_has_no_lock(self, tmp_path):
        from clasi.state_db import init_db

        db_path = tmp_path / "docs" / "clasi" / ".clasi.db"
        db_path.parent.mkdir(parents=True)
        init_db(db_path)
        _check_no_execution_lock(tmp_path)

    def test_raises_when_lock_held_legacy_path(self, tmp_path):
        from clasi.state_db import acquire_lock, init_db, register_sprint

        db_path = tmp_path / "docs" / "clasi" / ".clasi.db"
        db_path.parent.mkdir(parents=True)
        init_db(db_path)
        register_sprint(db_path, "001", "test-sprint")
        acquire_lock(db_path, "001")

        with pytest.raises(SystemExit) as exc_info:
            _check_no_execution_lock(tmp_path)
        assert exc_info.value.code == 1

    def test_raises_when_lock_held_explicit_paths(self, tmp_path):
        from clasi.state_db import acquire_lock, init_db, register_sprint

        db_path = tmp_path / ".clasi" / ".clasi.db"
        db_path.parent.mkdir(parents=True)
        init_db(db_path)
        register_sprint(db_path, "001", "test-sprint")
        acquire_lock(db_path, "001")

        with pytest.raises(SystemExit) as exc_info:
            _check_no_execution_lock(tmp_path, db_paths=[db_path])
        assert exc_info.value.code == 1

    def test_passes_when_explicit_paths_list_is_empty(self, tmp_path):
        # No db paths to check — should not raise.
        _check_no_execution_lock(tmp_path, db_paths=[])

    def test_skips_nonexistent_paths(self, tmp_path):
        nonexistent = tmp_path / "nonexistent" / ".clasi.db"
        # Should not raise even when path doesn't exist.
        _check_no_execution_lock(tmp_path, db_paths=[nonexistent])


# ---------------------------------------------------------------------------
# detect_moves
# ---------------------------------------------------------------------------


class TestDetectMovesNothingToDo:
    def test_empty_project_returns_empty(self, tmp_path):
        """No legacy files anywhere → detect_moves returns []."""
        project = _make_project(tmp_path)
        assert detect_moves(project) == []

    def test_config_pinned_to_current_locations(self, tmp_path):
        """When config pins categories to their actual locations, no moves needed."""
        # Create some files at .clasi/ locations.
        (tmp_path / ".clasi" / "issues").mkdir(parents=True)
        (tmp_path / ".clasi" / "issues" / "issue1.md").write_text("# Issue", encoding="utf-8")

        # Pin config so issues resolves to .clasi/issues (where files already are).
        project = _make_project(
            tmp_path,
            config_paths={
                "issues": ".clasi/issues",
                "sprints": ".clasi/sprints",
                "reflections": ".clasi/reflections",
                "architecture": ".clasi/architecture",
                "design": "docs/design",
                "logs": ".clasi/log",
                "db": ".clasi/.clasi.db",
            },
        )
        moves = detect_moves(project)
        # issues is already at .clasi/issues — should be skipped.
        assert all(m.category != "issues" for m in moves)

    def test_src_eq_dst_skipped(self, tmp_path):
        """If first candidate is the configured destination, skip."""
        # Seed .clasi/issues with a file.
        (tmp_path / ".clasi" / "issues").mkdir(parents=True)
        (tmp_path / ".clasi" / "issues" / "issue1.md").write_text("# x", encoding="utf-8")

        # Configure project so issues_dir resolves to .clasi/issues.
        project = _make_project(tmp_path, config_paths={"issues": ".clasi/issues"})
        moves = detect_moves(project)
        assert all(m.category != "issues" for m in moves)

    def test_empty_directory_skipped(self, tmp_path):
        """An existing but empty source directory yields no Move."""
        # Create empty .clasi/issues/
        (tmp_path / ".clasi" / "issues").mkdir(parents=True)
        # Default destination is clasi/issues — different path, but source is empty.
        project = _make_project(tmp_path)
        moves = detect_moves(project)
        assert all(m.category != "issues" for m in moves)


class TestDetectMovesFindsFiles:
    def test_finds_issues_in_dot_clasi(self, tmp_path):
        """Seed .clasi/issues with a file; default dst is clasi/issues."""
        (tmp_path / ".clasi" / "issues").mkdir(parents=True)
        (tmp_path / ".clasi" / "issues" / "issue1.md").write_text("# x", encoding="utf-8")

        # Default project (no config pin) → issues_dir = clasi/issues
        project = _make_project(tmp_path)
        moves = detect_moves(project)

        issue_moves = [m for m in moves if m.category == "issues"]
        assert len(issue_moves) == 1
        m = issue_moves[0]
        assert m.src == tmp_path / ".clasi" / "issues"
        assert m.dst == project.issues_dir
        assert m.is_file is False

    def test_finds_db_as_file(self, tmp_path):
        """DB candidate is probed as a file, not directory."""
        db = tmp_path / ".clasi" / ".clasi.db"
        db.parent.mkdir(parents=True)
        db.write_bytes(b"SQLite")

        # Configure destination elsewhere so we get a Move.
        project = _make_project(tmp_path, config_paths={"db": ".clasi/other/.clasi.db"})
        moves = detect_moves(project)

        db_moves = [m for m in moves if m.category == "db"]
        assert len(db_moves) == 1
        assert db_moves[0].is_file is True

    def test_mode_is_move_when_dst_absent(self, tmp_path):
        """mode should be 'move' when destination does not exist."""
        (tmp_path / ".clasi" / "issues").mkdir(parents=True)
        (tmp_path / ".clasi" / "issues" / "issue1.md").write_text("# x", encoding="utf-8")

        project = _make_project(tmp_path)
        moves = detect_moves(project)

        issue_moves = [m for m in moves if m.category == "issues"]
        assert issue_moves[0].mode == "move"

    def test_mode_is_merge_when_dst_non_empty(self, tmp_path):
        """mode should be 'merge' when destination already contains files."""
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        (src_dir / "issue1.md").write_text("# x", encoding="utf-8")

        # Pre-populate the destination.
        project = _make_project(tmp_path)
        dst_dir = project.issues_dir
        dst_dir.mkdir(parents=True)
        (dst_dir / "existing.md").write_text("# existing", encoding="utf-8")

        moves = detect_moves(project)
        issue_moves = [m for m in moves if m.category == "issues"]
        assert issue_moves[0].mode == "merge"

    def test_second_candidate_used_when_first_missing(self, tmp_path):
        """Falls back to the second candidate location."""
        legacy = tmp_path / "docs" / "clasi" / "issues"
        legacy.mkdir(parents=True)
        (legacy / "issue1.md").write_text("# x", encoding="utf-8")

        project = _make_project(tmp_path)
        moves = detect_moves(project)

        issue_moves = [m for m in moves if m.category == "issues"]
        assert len(issue_moves) == 1
        assert issue_moves[0].src == legacy


# ---------------------------------------------------------------------------
# execute_moves
# ---------------------------------------------------------------------------


class TestExecuteMovesPerformsMove:
    def test_file_moved_to_destination(self, tmp_path):
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        (src_dir / "issue1.md").write_text("# x", encoding="utf-8")

        project = _make_project(tmp_path)
        moves = detect_moves(project)
        assert moves

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            execute_moves(project, moves)

        dst_dir = project.issues_dir
        assert (dst_dir / "issue1.md").exists()
        assert not src_dir.exists()

    def test_idempotent(self, tmp_path):
        """Second detect_moves call returns [] after successful execute_moves."""
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        (src_dir / "issue1.md").write_text("# x", encoding="utf-8")

        project = _make_project(tmp_path)
        moves = detect_moves(project)

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            execute_moves(project, moves)

        moves2 = detect_moves(project)
        assert all(m.category != "issues" for m in moves2)

    def test_dry_run_leaves_files_unchanged(self, tmp_path):
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        (src_dir / "issue1.md").write_text("# x", encoding="utf-8")

        project = _make_project(tmp_path)
        moves = detect_moves(project)

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            execute_moves(project, moves, dry_run=True)

        # Source should still exist; destination should not have been created.
        assert (src_dir / "issue1.md").exists()
        assert not project.issues_dir.exists() or not any(project.issues_dir.iterdir())

    def test_merge_does_not_clobber_existing_file(self, tmp_path):
        """In merge mode, existing destination files are skipped."""
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        (src_dir / "conflict.md").write_text("from src", encoding="utf-8")
        (src_dir / "new.md").write_text("new file", encoding="utf-8")

        project = _make_project(tmp_path)
        dst_dir = project.issues_dir
        dst_dir.mkdir(parents=True)
        (dst_dir / "conflict.md").write_text("original", encoding="utf-8")

        moves = detect_moves(project)
        assert any(m.category == "issues" and m.mode == "merge" for m in moves)

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            execute_moves(project, moves)

        # Original should be preserved; new file should be moved.
        assert (dst_dir / "conflict.md").read_text(encoding="utf-8") == "original"
        assert (dst_dir / "new.md").read_text(encoding="utf-8") == "new file"

    @pytest.mark.slow  # 032/008: real git repo (_init_git_repo)
    def test_untracked_files_in_real_git_repo_fail_cleanly(self, tmp_path, capsys):
        """Regression: init crashed moving untracked artifacts in a git repo.

        Reproduces the ``clasi init`` failure — a real git repo whose
        ``.clasi/issues/*.md`` files were never committed. ``git mv`` on an
        untracked file exits 128 (``fatal: not under version control``),
        which previously aborted the whole migration with a raw traceback.
        It must now fail with an actionable ``SystemExit`` and move
        nothing.
        """
        _init_git_repo(tmp_path)
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        src_file = src_dir / "manufacturer-relation-followups.md"
        src_file.write_text("# followups", encoding="utf-8")
        (src_dir / ".gitkeep").write_text("", encoding="utf-8")

        project = _make_project(tmp_path)
        moves = detect_moves(project)
        assert moves

        # No mocking of _is_git_repo — exercise the real git path.
        with pytest.raises(SystemExit):
            execute_moves(project, moves)

        err = capsys.readouterr().err
        assert "not checked into git" in err
        assert "manufacturer-relation-followups.md" in err
        assert "commit" in err.lower()
        # Nothing moved: source intact, destination not created.
        assert src_file.exists()
        assert not (project.issues_dir / "manufacturer-relation-followups.md").exists()

    @pytest.mark.slow  # 032/008: real git repo (_init_git_repo)
    def test_committed_files_in_real_git_repo_move_via_git(self, tmp_path):
        """Once artifacts are committed, migration proceeds through git mv."""
        _init_git_repo(tmp_path)
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        (src_dir / "issue.md").write_text("# followups", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "-A"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "seed"],
            check=True,
            capture_output=True,
        )

        project = _make_project(tmp_path)
        moves = detect_moves(project)
        assert moves

        execute_moves(project, moves)

        assert (project.issues_dir / "issue.md").read_text(
            encoding="utf-8"
        ) == "# followups"
        assert not (src_dir / "issue.md").exists()

    def test_resets_project_db_when_db_moved(self, tmp_path):
        """project._db is reset to None after the DB file is moved."""
        from clasi.state_db import init_db

        db_src = tmp_path / ".clasi" / ".clasi.db"
        db_src.parent.mkdir(parents=True)
        init_db(db_src)  # create a valid SQLite database

        project = _make_project(tmp_path, config_paths={"db": ".clasi/other/.clasi.db"})

        # Simulate a live DB connection.
        project._db = MagicMock()

        moves = detect_moves(project)
        db_moves = [m for m in moves if m.category == "db"]
        assert db_moves

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            execute_moves(project, moves)

        assert project._db is None

    def test_empty_moves_list_is_noop(self, tmp_path):
        project = _make_project(tmp_path)
        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            execute_moves(project, [])
        # Should not raise.

    def test_gitignore_updated_for_log_move(self, tmp_path):
        """When logs are moved, .gitignore is updated accordingly."""
        log_src = tmp_path / ".clasi" / "log"
        log_src.mkdir(parents=True)
        (log_src / "session.log").write_text("log line", encoding="utf-8")

        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".clasi/log/\n", encoding="utf-8")

        # Configure destination to something different.
        project = _make_project(tmp_path, config_paths={"logs": "clasi/log"})
        moves = detect_moves(project)
        log_moves = [m for m in moves if m.category == "logs"]
        assert log_moves, "Expected a logs move to be detected"

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            execute_moves(project, moves)

        content = gitignore.read_text(encoding="utf-8")
        assert "clasi/log/" in content


# ---------------------------------------------------------------------------
# TestMergeModeCleansUpSourceDir — regression tests for sprint 017
# ---------------------------------------------------------------------------


class TestMergeModeCleansUpSourceDir:
    """Regression tests for the merge-mode source-directory cleanup fix.

    The bug: ``clasi init`` pre-creates destination dirs with ``.gitkeep``.
    The old ``detect_moves`` saw a non-empty destination and chose
    ``mode="merge"``, which left a ``.gitkeep`` in the source after moving
    real files.  ``_cleanup_empty_parents`` then failed to ``rmdir`` the
    non-empty source, leaving it behind.

    Fix 1 (detect_moves): treat a ``.gitkeep``-only destination as empty
    → ``mode="move"``.
    Fix 2 (execute_moves merge branch): unlink residual non-artifact files
    before calling ``_cleanup_empty_parents`` so the source is removed even
    when merge mode does fire.
    """

    def test_source_dir_removed_when_dest_has_only_gitkeep(self, tmp_path):
        """Exact bug scenario: init pre-creates dest with .gitkeep, forcing
        merge mode; after migration the source dir must be completely gone."""
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        (src_dir / "idea.md").write_text("# My idea", encoding="utf-8")

        project = _make_project(tmp_path)
        dst_dir = project.issues_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        (dst_dir / ".gitkeep").touch()  # simulates what clasi init scaffolds

        moves = detect_moves(project)
        assert any(m.category == "issues" for m in moves), "Expected an issues move"

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            execute_moves(project, moves)

        assert (dst_dir / "idea.md").exists(), "Artifact must reach destination"
        assert not src_dir.exists(), "Source dir must be fully removed"

    def test_detect_moves_treats_gitkeep_only_dest_as_move_mode(self, tmp_path):
        """detect_moves returns mode='move' when dest contains only .gitkeep."""
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        (src_dir / "idea.md").write_text("# idea", encoding="utf-8")

        project = _make_project(tmp_path)
        dst_dir = project.issues_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        (dst_dir / ".gitkeep").touch()

        moves = detect_moves(project)
        issues_move = next(m for m in moves if m.category == "issues")
        assert issues_move.mode == "move", (
            f"Expected mode='move' for gitkeep-only dest; got '{issues_move.mode}'"
        )

    def test_no_clobber_preserved_in_merge_with_real_dst_file(self, tmp_path):
        """A real artifact in dest still triggers merge mode (no-clobber)."""
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        (src_dir / "conflict.md").write_text("from src", encoding="utf-8")

        project = _make_project(tmp_path)
        dst_dir = project.issues_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        (dst_dir / "conflict.md").write_text("original", encoding="utf-8")

        moves = detect_moves(project)
        issues_move = next(m for m in moves if m.category == "issues")
        assert issues_move.mode == "merge", (
            "Real dst artifact must force merge mode"
        )

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            execute_moves(project, moves)

        assert (dst_dir / "conflict.md").read_text(encoding="utf-8") == "original", (
            "Existing dst file must not be clobbered"
        )

    def test_docs_category_source_removed_when_dest_has_only_gitkeep(self, tmp_path):
        """Regression for a docs/-target category (architecture): source dir
        removed after merge-mode migration when dest has only .gitkeep.

        The "architecture" category's destination is design_dir (no
        dedicated architecture_dir property exists anymore)."""
        src_dir = tmp_path / ".clasi" / "architecture"
        src_dir.mkdir(parents=True)
        (src_dir / "arch.md").write_text("# Architecture", encoding="utf-8")

        project = _make_project(tmp_path)
        dst_dir = project.design_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        (dst_dir / ".gitkeep").touch()

        moves = detect_moves(project)
        assert any(m.category == "architecture" for m in moves), (
            "Expected an architecture move"
        )

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            execute_moves(project, moves)

        assert (dst_dir / "arch.md").exists(), "Artifact must reach destination"
        assert not src_dir.exists(), "Source dir must be fully removed"

    def test_dot_clasi_itself_still_exists_after_migration(self, tmp_path):
        """The .clasi/ root must survive even after its issues/ sub-dir is cleaned
        up, provided .clasi/ has other content (e.g. a config.yaml)."""
        import yaml

        # Write a config so .clasi/ is non-empty after issues/ is removed.
        dot_clasi = tmp_path / ".clasi"
        dot_clasi.mkdir(parents=True, exist_ok=True)
        config_file = dot_clasi / "config.yaml"
        config_file.write_text(yaml.dump({"process": "se", "paths": {}}), encoding="utf-8")

        src_dir = dot_clasi / "issues"
        src_dir.mkdir(parents=True)
        (src_dir / "x.md").write_text("# x", encoding="utf-8")

        project = _make_project(tmp_path)
        dst_dir = project.issues_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        (dst_dir / ".gitkeep").touch()

        moves = detect_moves(project)
        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            execute_moves(project, moves)

        assert not src_dir.exists(), "Source issues/ sub-dir must be removed"
        assert dot_clasi.exists(), ".clasi/ root must still exist (config.yaml is there)"


# ---------------------------------------------------------------------------
# run_migrate
# ---------------------------------------------------------------------------


class TestRunMigrateNothingToDo:
    def test_nothing_to_do(self, tmp_path):
        """run_migrate reports 'nothing to do' when no legacy files exist."""
        project = _make_project(tmp_path)

        with patch("clasi.migrate_command.run_init"):
            run_migrate(str(tmp_path))
        # Should not raise.

    def test_nothing_to_do_message(self, tmp_path, capsys):
        """run_migrate prints 'nothing to migrate' message."""
        project = _make_project(tmp_path)

        with patch("clasi.migrate_command.run_init"):
            run_migrate(str(tmp_path))

        captured = capsys.readouterr()
        assert "nothing" in captured.out.lower() or "already" in captured.out.lower()


class TestRunMigrateLegacyDocsClasi:
    def test_moves_docs_clasi_issues(self, tmp_path):
        """Legacy docs/clasi/ layout is detected and moved."""
        legacy_issues = tmp_path / "docs" / "clasi" / "issues"
        legacy_issues.mkdir(parents=True)
        (legacy_issues / "issue1.md").write_text("# Issue", encoding="utf-8")

        # Default project (no config pin) → issues_dir = clasi/issues
        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init"):
                run_migrate(str(tmp_path))

        project = Project(tmp_path)
        assert (project.issues_dir / "issue1.md").exists()
        assert not (legacy_issues / "issue1.md").exists()

    def test_legacy_full_tree_moves(self, tmp_path):
        """Seed multiple legacy docs/clasi/ categories; all are migrated."""
        docs_clasi = tmp_path / "docs" / "clasi"
        for cat in ["issues", "sprints", "architecture"]:
            cat_dir = docs_clasi / cat
            cat_dir.mkdir(parents=True)
            (cat_dir / "file.md").write_text(f"# {cat}", encoding="utf-8")

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init"):
                run_migrate(str(tmp_path))

        project = Project(tmp_path)
        assert (project.issues_dir / "file.md").exists()
        assert (project.sprints_dir / "file.md").exists()
        # "architecture" has no dedicated destination property anymore —
        # legacy architecture content merges into design_dir.
        assert (project.design_dir / "file.md").exists()

    def test_calls_run_init(self, tmp_path):
        """run_migrate calls run_init after migration, when Claude is
        already installed (.claude/ exists) — refreshing an
        already-installed platform, not force-installing a new one."""
        legacy_issues = tmp_path / "docs" / "clasi" / "issues"
        legacy_issues.mkdir(parents=True)
        (legacy_issues / "issue1.md").write_text("# x", encoding="utf-8")
        (tmp_path / ".claude").mkdir()  # Claude platform already installed

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init") as mock_init:
                run_migrate(str(tmp_path))

        mock_init.assert_called_once()

    def test_skips_run_init_when_no_platform_installed(self, tmp_path):
        """run_migrate does not force-install Claude into a repo that
        never opted into it — `run_init` is only called to refresh
        platforms actually installed (as of this ticket, effectively
        "Claude, if .claude/ exists"). Previously `run_migrate` always
        finished with `run_init(target, claude=True)` unconditionally,
        force-installing Claude even on a repo with no .claude/ at all
        (ticket 032/004, review finding F11)."""
        legacy_issues = tmp_path / "docs" / "clasi" / "issues"
        legacy_issues.mkdir(parents=True)
        (legacy_issues / "issue1.md").write_text("# x", encoding="utf-8")
        assert not (tmp_path / ".claude").exists()

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init") as mock_init:
                run_migrate(str(tmp_path))

        mock_init.assert_not_called()

    def test_prints_restart_notice(self, tmp_path, capsys):
        """run_migrate prints a restart notice after migration."""
        legacy_issues = tmp_path / "docs" / "clasi" / "issues"
        legacy_issues.mkdir(parents=True)
        (legacy_issues / "issue1.md").write_text("# x", encoding="utf-8")

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init"):
                run_migrate(str(tmp_path))

        captured = capsys.readouterr()
        assert "restart" in captured.out.lower()


class TestRunMigrateNonGit:
    def test_moves_files_without_git(self, tmp_path):
        """run_migrate works in a non-git directory (uses shutil.move)."""
        legacy_issues = tmp_path / "docs" / "clasi" / "issues"
        legacy_issues.mkdir(parents=True)
        (legacy_issues / "issue.md").write_text("# Issue", encoding="utf-8")

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init"):
                run_migrate(str(tmp_path))

        project = Project(tmp_path)
        assert (project.issues_dir / "issue.md").exists()


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestMigrateCliCommand:
    def test_migrate_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["migrate", "--help"])
        assert result.exit_code == 0
        assert "migrate" in result.output.lower()

    def test_migrate_succeeds_nothing_to_do(self, tmp_path):
        """CLI migrate exits 0 when there is nothing to migrate."""
        runner = CliRunner()
        with patch("clasi.migrate_command.run_init"):
            result = runner.invoke(cli, ["migrate", str(tmp_path)])
        assert result.exit_code == 0, result.output

    def test_migrate_succeeds_non_git(self, tmp_path):
        """CLI migrate moves legacy files and exits 0."""
        legacy_issues = tmp_path / "docs" / "clasi" / "issues"
        legacy_issues.mkdir(parents=True)
        (legacy_issues / "issue.md").write_text("# x", encoding="utf-8")

        runner = CliRunner()
        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init"):
                result = runner.invoke(cli, ["migrate", str(tmp_path)])

        assert result.exit_code == 0, result.output
        project = Project(tmp_path)
        assert (project.issues_dir / "issue.md").exists()

    def test_migrate_prints_restart_notice(self, tmp_path):
        """CLI migrate prints restart notice after a successful migration."""
        legacy_issues = tmp_path / "docs" / "clasi" / "issues"
        legacy_issues.mkdir(parents=True)
        (legacy_issues / "issue.md").write_text("# x", encoding="utf-8")

        runner = CliRunner()
        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            with patch("clasi.migrate_command.run_init"):
                result = runner.invoke(cli, ["migrate", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert "restart" in result.output.lower()
