"""Tests for the HEAD-sha test-pass marker (sprint 031 ticket 008).

`close_sprint`'s internal test run is now the sprint's *only* full-suite
run (execution.md's separate pre-close run and sprint-review's
independent re-run are both gone -- see the sprint-review and execution
doc changes this ticket also makes). This marker exists for the residual
case that redundancy fix does not cover on its own: a step *after*
"tests" fails with no recorded recovery pointer (e.g. `Sprint.archive()`,
which has no `_write_recovery` call because it is idempotent by its own
ground truth -- see close.py's module docstring), so a naive retry would
re-run the already-passed suite for real, tempting the operator toward a
fake `test_command` exactly as the ticket's motivating incident describes.

Two things are exercised here:

1. An end-to-end scenario (real scratch git repo, real subprocess test
   run via a counter script, exactly like test_close_sprint_resumability.py)
   proving the marker -- not the pre-existing resume-index mechanism --
   is what allows a second close_sprint call to skip a redundant real
   run when no recovery pointer exists at all.
2. Focused checks of `SprintCloser._valid_test_pass_marker` proving the
   design caution from the ticket: a marker is trusted only when the
   HEAD sha, the test command, AND working-tree cleanliness *all* still
   match at read time -- a dirty tree at a matching sha is never trusted,
   nor is a matching tree at a different sha or a different command.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from clasi.close import SprintCloser
from clasi.frontmatter import write_frontmatter
from clasi.mcp_server import set_project
from clasi.project import Project
from clasi.sprint import Sprint
from clasi.state_db import acquire_lock, advance_phase, get_recovery_state, get_test_pass_marker, record_gate
from clasi.tools.artifact_tools import (
    close_sprint,
    create_sprint,
    create_ticket,
    move_ticket_to_done,
    update_ticket_status,
)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-b", "master", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True, capture_output=True)


def _git_commit(root: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", message], cwd=root, check=True, capture_output=True)


def _head_sha(root: Path) -> str:
    return _run(["git", "rev-parse", "HEAD"], root).stdout.strip()


@pytest.fixture
def work_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real, scratch git repository -- never this repo's own sprint 031.

    Writes a ``.gitignore`` covering the state DB, mirroring every real
    ``clasi init`` project (see this repo's own ``.gitignore``: both
    ``.clasi.db`` and ``.clasi/.clasi.db`` are ignored there). Without
    this, writing the marker itself would make ``git status --porcelain``
    report an untracked ``.clasi/.clasi.db`` and every clean-tree check
    in this file would spuriously fail -- not a marker-logic bug, but a
    fixture omission this repo's own layout already tells us to avoid.
    """
    root = tmp_path / "repo"
    root.mkdir()
    _git_init(root)

    (root / "pyproject.toml").write_text(
        '[project]\nname = "marker-dry-run"\nversion = "0.20260101.1"\n',
        encoding="utf-8",
    )
    (root / ".gitignore").write_text(
        ".clasi.db\n.clasi/.clasi.db\n.clasi/log/\n", encoding="utf-8",
    )
    clasi_dir = root / ".clasi"
    clasi_dir.mkdir(parents=True, exist_ok=True)
    (clasi_dir / "config.yaml").write_text("process: se\n", encoding="utf-8")
    _git_commit(root, "initial")

    monkeypatch.chdir(root)
    set_project(root)
    return root


def _advance_to_ticketing(work_dir: Path, sprint_id: str) -> None:
    db_path = work_dir / ".clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # roadmap -> planning-docs
    advance_phase(db_path, sprint_id)  # planning-docs -> architecture-review
    record_gate(db_path, sprint_id, "architecture_review", "passed")
    advance_phase(db_path, sprint_id)  # architecture-review -> ticketing (031/002)
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")


def _write_test_counter_script(outside_dir: Path) -> tuple[str, Path]:
    """A tiny script that increments a counter file each time it is
    actually invoked and exits 0 -- a real subprocess spy, matching
    test_close_sprint_resumability.py's technique.

    Written to *outside_dir*, which must be outside the scratch git repo
    (e.g. the pytest tmp_path itself, not work_dir) -- unlike the
    resumability test, this file's tests care about working-tree
    cleanliness, and an uncommitted script + counter file sitting inside
    the repo would make every close_sprint call's tree look dirty for
    reasons that have nothing to do with the marker being exercised.
    """
    script = outside_dir / "_count_test_runs.py"
    script.write_text(
        "import pathlib, sys\n"
        "p = pathlib.Path(sys.argv[1])\n"
        "n = int(p.read_text()) if p.exists() else 0\n"
        "p.write_text(str(n + 1))\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    counter_file = outside_dir / "_test_run_count.txt"
    test_command = f"{sys.executable} {script} {counter_file}"
    return test_command, counter_file


class TestMarkerSkipsRedundantRealRun:
    """End-to-end: the marker (not the resume-index mechanism) lets a
    second close_sprint call skip a real test run when no recovery
    pointer exists at all."""

    def test_marker_skip_survives_a_recovery_less_failure(
        self, work_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        create_result = json.loads(create_sprint("Marker Dry Run"))
        sprint_id = create_result["id"]
        sprint_dir = Path(create_result["path"])
        branch_name = create_result["branch"]

        write_frontmatter(
            sprint_dir / "sprint.md",
            {
                "id": sprint_id,
                "title": "Marker Dry Run",
                "status": "active",
                "branch": branch_name,
            },
        )

        _advance_to_ticketing(work_dir, sprint_id)
        create_ticket(sprint_id, "Do the thing")
        ticket_path = sprint_dir / "tickets" / "001-do-the-thing.md"
        assert ticket_path.exists()

        db_path = work_dir / ".clasi" / ".clasi.db"
        acquire_lock(db_path, sprint_id)
        advance_phase(db_path, sprint_id)  # ticketing -> executing

        _run(["git", "checkout", "-b", branch_name], work_dir)
        (work_dir / "feature.py").write_text("# ticket work\n", encoding="utf-8")
        update_ticket_status(str(ticket_path), "done")
        move_ticket_to_done(str(ticket_path))
        _git_commit(work_dir, f"feat: implement ticket ({sprint_id}-001)")

        test_command, counter_file = _write_test_counter_script(tmp_path)

        # --- Fail Sprint.archive() exactly once. Unlike merge_branch (used
        # by test_close_sprint_resumability.py), archive() has no
        # surrounding try/except in SprintCloser.run() -- it is treated as
        # idempotent-by-ground-truth and never calls _write_recovery. A
        # crash here therefore leaves NO recovery pointer behind, which is
        # exactly the gap the resume-index mechanism cannot cover and the
        # marker exists to close.
        real_archive = Sprint.archive
        archive_calls = {"n": 0}

        def _flaky_archive(self):
            archive_calls["n"] += 1
            if archive_calls["n"] == 1:
                raise RuntimeError("simulated archive failure (injected by test)")
            return real_archive(self)

        monkeypatch.setattr(Sprint, "archive", _flaky_archive)

        # ==================== Attempt 1: tests pass for real, archive crashes ====================
        with pytest.raises(RuntimeError, match="simulated archive failure"):
            close_sprint(
                sprint_id=sprint_id,
                branch_name=branch_name,
                main_branch="master",
                push_tags=False,
                delete_branch=False,
                test_command=test_command,
            )

        assert counter_file.read_text(encoding="utf-8").strip() == "1", (
            "tests must have run for real exactly once on attempt 1"
        )

        # No recovery pointer was written -- proves the pre-existing
        # resume-index mechanism has nothing to say about attempt 2.
        assert get_recovery_state(db_path) is None, (
            "archive() has no _write_recovery call; a bare crash there "
            "must leave no recovery pointer"
        )

        # The marker was written, keyed to the real HEAD sha and the
        # exact test command used.
        marker = get_test_pass_marker(db_path, sprint_id)
        assert marker is not None
        assert marker["head_sha"] == _head_sha(work_dir)
        assert marker["test_cmd"] == test_command

        # ==================== Attempt 2: retry, archive now succeeds ====================
        attempt2 = json.loads(
            close_sprint(
                sprint_id=sprint_id,
                branch_name=branch_name,
                main_branch="master",
                push_tags=False,
                delete_branch=False,
                test_command=test_command,
            )
        )

        assert attempt2["status"] == "success", attempt2

        # The tests step was skipped via the marker, not re-run for real.
        assert counter_file.read_text(encoding="utf-8").strip() == "1", (
            "the tests step must not re-run on retry -- the marker proves "
            "it already passed at this exact HEAD sha with a clean tree"
        )
        assert any("already passed for HEAD" in r for r in attempt2["repairs"]), attempt2["repairs"]

        # The marker is cleared once the sprint fully closes -- it can
        # never be consulted again for an archived sprint id.
        assert get_test_pass_marker(db_path, sprint_id) is None


class TestValidTestPassMarker:
    """Focused checks of SprintCloser._valid_test_pass_marker against a
    real scratch git repo -- the design-caution cases from the ticket:
    sha match, test_cmd match, AND a clean tree are all required."""

    def _closer(self, work_dir: Path) -> SprintCloser:
        project = Project(work_dir)
        return SprintCloser(
            project,
            sprint_id="999",
            branch_name="sprint/999-x",
            main_branch="master",
            push_tags_flag=False,
            delete_branch_flag=False,
        )

    def test_valid_when_sha_and_cmd_match_and_tree_clean(self, work_dir: Path) -> None:
        from clasi.state_db import record_test_pass_marker

        sha = _head_sha(work_dir)
        db_path = work_dir / ".clasi" / ".clasi.db"
        record_test_pass_marker(db_path, "999", sha, "uv run pytest")

        closer = self._closer(work_dir)
        assert closer._valid_test_pass_marker("999", "uv run pytest") == sha

    def test_invalid_when_tree_is_dirty(self, work_dir: Path) -> None:
        from clasi.state_db import record_test_pass_marker

        sha = _head_sha(work_dir)
        db_path = work_dir / ".clasi" / ".clasi.db"
        record_test_pass_marker(db_path, "999", sha, "uv run pytest")

        (work_dir / "uncommitted.txt").write_text("dirty\n", encoding="utf-8")

        closer = self._closer(work_dir)
        assert closer._valid_test_pass_marker("999", "uv run pytest") is None, (
            "a dirty working tree at a matching sha is NOT the same code "
            "as what the marker certified"
        )

    def test_invalid_when_test_cmd_differs(self, work_dir: Path) -> None:
        from clasi.state_db import record_test_pass_marker

        sha = _head_sha(work_dir)
        db_path = work_dir / ".clasi" / ".clasi.db"
        record_test_pass_marker(db_path, "999", sha, "uv run pytest")

        closer = self._closer(work_dir)
        assert closer._valid_test_pass_marker("999", "npm test") is None, (
            "a marker recorded for one test command must not license "
            "skipping a different one"
        )

    def test_invalid_when_head_has_moved(self, work_dir: Path) -> None:
        from clasi.state_db import record_test_pass_marker

        sha = _head_sha(work_dir)
        db_path = work_dir / ".clasi" / ".clasi.db"
        record_test_pass_marker(db_path, "999", sha, "uv run pytest")

        _git_commit(work_dir, "a new commit moves HEAD")

        closer = self._closer(work_dir)
        assert closer._valid_test_pass_marker("999", "uv run pytest") is None

    def test_invalid_when_no_marker_recorded(self, work_dir: Path) -> None:
        closer = self._closer(work_dir)
        assert closer._valid_test_pass_marker("999", "uv run pytest") is None
