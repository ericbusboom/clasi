"""Unit tests for _sweep_done_issues shared helper.

Tests the module-level helper that scans sprint-scoped and pending-pool
issues and completes any whose tickets are all done.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clasi.tools.artifact_tools import (
    _sweep_done_issues,
    close_sprint,
    create_sprint,
    create_ticket,
)
from clasi.frontmatter import read_frontmatter, write_frontmatter
from clasi.issue import Issue
from clasi.mcp_server import set_project, get_project
from clasi.project import Project
from clasi.sprint import Sprint
from clasi.state_db import (
    acquire_lock,
    advance_phase,
    record_gate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _advance_to_ticketing(work_dir, sprint_id: str) -> None:
    db_path = work_dir / ".clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # roadmap -> planning-docs
    advance_phase(db_path, sprint_id)  # planning-docs -> architecture-review
    record_gate(db_path, sprint_id, "architecture_review", "passed")
    advance_phase(db_path, sprint_id)  # architecture-review -> stakeholder-review
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")
    advance_phase(db_path, sprint_id)  # stakeholder-review -> ticketing


def _advance_to_executing(work_dir, sprint_id: str) -> None:
    _advance_to_ticketing(work_dir, sprint_id)
    db_path = work_dir / ".clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # ticketing -> executing
    acquire_lock(db_path, sprint_id)


def _find_sprint_dir(work_dir, sprint_id: str = "001") -> Path:
    sprints_dir = work_dir / ".clasi" / "sprints"
    for d in sorted(sprints_dir.iterdir()):
        if d.is_dir() and d.name.startswith(sprint_id + "-"):
            return d
    raise ValueError(f"Sprint dir for {sprint_id!r} not found")


def _mark_ticket_done(ticket_path: str) -> None:
    """Set a ticket's frontmatter status to 'done'."""
    p = Path(ticket_path)
    fm = read_frontmatter(p)
    fm["status"] = "done"
    write_frontmatter(p, fm)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_LEGACY_PATHS_PIN = """\
process: se
paths:
  issues: .clasi/issues
  sprints: .clasi/sprints
  reflections: .clasi/reflections
  architecture: .clasi/architecture
  design: docs/design
  logs: .clasi/log
  db: .clasi/.clasi.db
"""


def _write_legacy_pin(root: Path) -> None:
    """Write a backward-compat config.yaml pinning paths to .clasi/ layout."""
    clasi_dir = root / ".clasi"
    clasi_dir.mkdir(parents=True, exist_ok=True)
    (clasi_dir / "config.yaml").write_text(_LEGACY_PATHS_PIN, encoding="utf-8")


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    _write_legacy_pin(tmp_path)
    monkeypatch.chdir(tmp_path)
    set_project(tmp_path)
    return tmp_path


@pytest.fixture
def sprint_and_project(work_dir):
    """Return (sprint, project) after creating sprint 001 in ticketing phase."""
    create_sprint("Test Sprint")
    _advance_to_ticketing(work_dir, "001")
    proj = Project(work_dir)
    sprint = proj.get_sprint("001")
    return sprint, proj


# ---------------------------------------------------------------------------
# Tests: sprint-scoped issues
# ---------------------------------------------------------------------------


class TestSweepSprintScopedIssues:
    """Sweep completes sprint-scoped issues when all tickets are done."""

    def test_single_in_progress_issue_all_tickets_done(self, work_dir, sprint_and_project):
        """Sprint-scoped issue with all tickets done is moved to done/."""
        sprint, proj = sprint_and_project

        # Create a sprint-scoped issue via create_ticket
        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "feature.md").write_text(
            "---\nstatus: pending\n---\n\n# Feature\n", encoding="utf-8"
        )
        result = json.loads(create_ticket("001", "Implement Feature", issue="feature.md"))
        ticket_path = result["path"]

        # Mark the ticket done
        _mark_ticket_done(ticket_path)

        # Reload sprint to get fresh state
        sprint = proj.get_sprint("001")

        completed = _sweep_done_issues(sprint)

        assert "feature.md" in completed

        sprint_issues_dir = sprint.path / "issues"
        assert not (sprint_issues_dir / "feature.md").exists(), (
            "Issue must not remain in issues/ after sweep"
        )
        assert (sprint_issues_dir / "done" / "feature.md").exists(), (
            "Issue must be in issues/done/ after sweep"
        )
        fm = read_frontmatter(sprint_issues_dir / "done" / "feature.md")
        assert fm["status"] == "done"

    def test_issue_with_some_tickets_not_done_stays(self, work_dir, sprint_and_project):
        """Sprint-scoped issue stays in-progress when not all tickets are done."""
        sprint, proj = sprint_and_project

        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "feature.md").write_text(
            "---\nstatus: pending\n---\n\n# Feature\n", encoding="utf-8"
        )
        result1 = json.loads(create_ticket("001", "Part 1", issue="feature.md"))
        json.loads(create_ticket("001", "Part 2", issue="feature.md"))

        # Only mark ticket 1 done
        _mark_ticket_done(result1["path"])

        sprint = proj.get_sprint("001")
        completed = _sweep_done_issues(sprint)

        assert completed == []
        sprint_issues_dir = sprint.path / "issues"
        assert (sprint_issues_dir / "feature.md").exists()

    def test_completes_issue_suppressed_by_completes_issue_false(self, work_dir, sprint_and_project):
        """Issue with completes_issue: false on a ticket is not completed."""
        sprint, proj = sprint_and_project

        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "feature.md").write_text(
            "---\nstatus: pending\n---\n\n# Feature\n", encoding="utf-8"
        )
        result = json.loads(create_ticket("001", "Implement Feature", issue="feature.md"))
        ticket_path = result["path"]

        # Set completes_issue: false and mark done
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        fm["completes_issue"] = {"feature.md": False}
        write_frontmatter(Path(ticket_path), fm)

        sprint = proj.get_sprint("001")
        completed = _sweep_done_issues(sprint)

        assert completed == []
        sprint_issues_dir = sprint.path / "issues"
        assert (sprint_issues_dir / "feature.md").exists()

    def test_issue_already_in_done_not_included(self, work_dir, sprint_and_project):
        """Issues already in issues/done/ are skipped without error."""
        sprint, proj = sprint_and_project

        # Manually place an issue in done/
        issues_done = sprint.path / "issues" / "done"
        issues_done.mkdir(parents=True, exist_ok=True)
        (issues_done / "old.md").write_text(
            "---\nstatus: done\nsprint: '001'\ntickets: []\n---\n\n# Old\n",
            encoding="utf-8",
        )

        sprint = proj.get_sprint("001")
        completed = _sweep_done_issues(sprint)

        assert "old.md" not in completed

    def test_issue_with_no_tickets_not_completed(self, work_dir, sprint_and_project):
        """In-progress issue with an empty tickets list is not completed."""
        sprint, proj = sprint_and_project

        # Place issue directly in sprint issues dir with no ticket refs
        sprint_issues_dir = sprint.path / "issues"
        sprint_issues_dir.mkdir(parents=True, exist_ok=True)
        (sprint_issues_dir / "empty.md").write_text(
            "---\nstatus: in-progress\nsprint: '001'\ntickets: []\n---\n\n# Empty\n",
            encoding="utf-8",
        )

        sprint = proj.get_sprint("001")
        completed = _sweep_done_issues(sprint)

        assert completed == []
        assert (sprint_issues_dir / "empty.md").exists()

    def test_returns_empty_list_when_no_issues(self, work_dir, sprint_and_project):
        """Returns [] when the sprint has no issues at all."""
        sprint, proj = sprint_and_project
        sprint = proj.get_sprint("001")
        completed = _sweep_done_issues(sprint)
        assert completed == []

    def test_idempotent_no_error_on_repeat_call(self, work_dir, sprint_and_project):
        """Calling sweep twice does not error and returns [] on the second call."""
        sprint, proj = sprint_and_project

        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "feature.md").write_text(
            "---\nstatus: pending\n---\n\n# Feature\n", encoding="utf-8"
        )
        result = json.loads(create_ticket("001", "Task", issue="feature.md"))
        _mark_ticket_done(result["path"])

        sprint = proj.get_sprint("001")
        first = _sweep_done_issues(sprint)
        assert "feature.md" in first

        sprint = proj.get_sprint("001")
        second = _sweep_done_issues(sprint)
        assert second == []


# ---------------------------------------------------------------------------
# Tests: pending-pool issues
# ---------------------------------------------------------------------------


class TestSweepPendingPoolIssues:
    """Sweep relocates pending-pool issues to <sprint>/issues/done/ when done."""

    def test_pending_pool_issue_relocated_to_sprint_done(self, work_dir, sprint_and_project):
        """Pending-pool issue tagged with sprint is relocated to sprint issues/done/."""
        sprint, proj = sprint_and_project

        # Place an in-progress issue in the pending pool (tagged with sprint 001)
        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "pool-issue.md").write_text(
            "---\nstatus: in-progress\nsprint: '001'\ntickets: ['001-001']\n---\n\n# Pool Issue\n",
            encoding="utf-8",
        )

        # Manufacture a done ticket in sprint 001 so _is_ticket_done returns True.
        # We do this by creating a ticket and marking it done in the sprint.
        result = json.loads(create_ticket("001", "Pool Task"))
        ticket_path = result["path"]
        # Manually set ticket id in frontmatter so _is_ticket_done resolves correctly
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        fm["id"] = "001"
        write_frontmatter(Path(ticket_path), fm)
        # Move ticket file into done/ so get_ticket finds it
        done_dir = Path(ticket_path).parent / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.move(ticket_path, done_dir / Path(ticket_path).name)

        sprint = proj.get_sprint("001")
        completed = _sweep_done_issues(sprint)

        assert "pool-issue.md" in completed

        # File must be in sprint's issues/done/, not pool's done/
        sprint_done = sprint.path / "issues" / "done"
        assert (sprint_done / "pool-issue.md").exists(), (
            "Pending-pool issue must be relocated to <sprint>/issues/done/"
        )
        assert not (pending_pool / "pool-issue.md").exists(), (
            "Issue must not remain in pending pool after sweep"
        )
        assert not (pending_pool / "done" / "pool-issue.md").exists(), (
            "Issue must not go to pool's done/"
        )

        fm = read_frontmatter(sprint_done / "pool-issue.md")
        assert fm["status"] == "done"

    def test_pending_pool_issue_different_sprint_not_swept(self, work_dir, sprint_and_project):
        """Pending-pool issue tagged with a different sprint is not swept."""
        sprint, proj = sprint_and_project

        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "other.md").write_text(
            "---\nstatus: in-progress\nsprint: '099'\ntickets: []\n---\n\n# Other\n",
            encoding="utf-8",
        )

        sprint = proj.get_sprint("001")
        completed = _sweep_done_issues(sprint)

        assert completed == []
        assert (pending_pool / "other.md").exists()


# ---------------------------------------------------------------------------
# Tests: _close_sprint_full non-blocking issue handling (Sprint 014 ticket 003, A2)
# ---------------------------------------------------------------------------


def _mock_ok(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    """Return a MagicMock simulating a successful subprocess.CompletedProcess."""
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


_FULL_CLOSE_SUBPROCESS_SIDE_EFFECTS = [
    _mock_ok(0, "all tests passed"),  # pytest
    _mock_ok(0),                       # git config rebase.autoStash (version bump prep)
    _mock_ok(0),                       # git add <archive paths + version file> (version bump)
    _mock_ok(0),                       # git commit (version bump)
    _mock_ok(0, ""),                   # git status --porcelain (clean)
    _mock_ok(0),                       # git rev-parse --verify branch (merge check)
    _mock_ok(0),                       # git merge-base --is-ancestor (already merged)
    _mock_ok(0),                       # git push --tags
    _mock_ok(0),                       # git rev-parse --verify branch (delete check)
    _mock_ok(0),                       # git branch -d
    _mock_ok(0, "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"),  # git worktree list --porcelain (main only)
]


class TestCloseSprintFullIssueHandling:
    """_close_sprint_full (full lifecycle) issue handling — Sprint 014 A2 tests.

    Verifies:
    - An in-progress unresolved issue returns status: success (not error) and
      populates unresolved_issues in the result.
    - A deferred issue (completes_issue: false) does not block close and the
      result has status: success.
    """

    @pytest.fixture
    def work_dir(self, tmp_path, monkeypatch):
        _write_legacy_pin(tmp_path)
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        return tmp_path

    def _advance_to_executing(self, work_dir: Path, sprint_id: str) -> None:
        """Advance sprint to executing phase: acquire lock then advance."""
        db_path = work_dir / ".clasi" / ".clasi.db"
        _advance_to_ticketing(work_dir, sprint_id)
        acquire_lock(db_path, sprint_id)           # lock must come before advance
        advance_phase(db_path, sprint_id)          # ticketing -> executing

    def _sprint_dir(self, work_dir: Path, sprint_id: str = "001") -> Path:
        sprints_dir = work_dir / ".clasi" / "sprints"
        for d in sorted(sprints_dir.iterdir()):
            if d.is_dir() and d.name.startswith(sprint_id + "-"):
                return d
        raise ValueError(f"Sprint dir for {sprint_id!r} not found")

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260627.1")
    @patch("subprocess.run")
    def test_full_close_unresolved_issue_returns_success(
        self, mock_run, mock_ver, mock_tag, mock_reconcile, work_dir
    ):
        """_close_sprint_full with an in-progress unresolved issue returns success.

        An issue that is in the sprint issues dir with status: in-progress and
        is NOT deferred must NOT cause close_sprint to return status: error.
        The result must have status: success and include the issue filename in
        unresolved_issues.

        This tests the Sprint 014 A2 fix: the hard-fail block was replaced with
        collect-and-continue, mirroring _close_sprint_legacy.
        """
        create_sprint("Sprint")
        self._advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n', encoding="utf-8"
        )

        sprint_dir = self._sprint_dir(work_dir, "001")
        issues_dir = sprint_dir / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        # Place in-progress issue directly — no ticket references it, so not deferred
        (issues_dir / "unresolved.md").write_text(
            "---\nstatus: in-progress\nsprint: '001'\n---\n\n# Unresolved\n",
            encoding="utf-8",
        )

        mock_run.side_effect = list(_FULL_CLOSE_SUBPROCESS_SIDE_EFFECTS)
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))

        assert result.get("status") == "success", (
            f"Expected status: success but got: {result}"
        )
        assert "unresolved.md" in result.get("unresolved_issues", []), (
            f"Expected 'unresolved.md' in unresolved_issues, got: {result}"
        )

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260627.2")
    @patch("subprocess.run")
    def test_full_close_deferred_issue_does_not_block(
        self, mock_run, mock_ver, mock_tag, mock_reconcile, work_dir
    ):
        """_close_sprint_full with a deferred issue closes cleanly.

        A ticket has completes_issue: false for its issue. The precondition check
        (step 1b) should detect the deferred flag via _issue_is_deferred and skip
        the issue — close must succeed without error and without adding the
        issue to unresolved_issues.
        """
        from clasi.tools.artifact_tools import move_ticket_to_done, update_ticket_status

        create_sprint("Sprint")
        self._advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n', encoding="utf-8"
        )

        # Create an issue in the pending pool and link it via create_ticket
        issues_dir = work_dir / ".clasi" / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        (issues_dir / "deferred.md").write_text(
            "---\nstatus: pending\n---\n\n# Deferred\n", encoding="utf-8"
        )

        result = json.loads(create_ticket("001", "Partial Work", issue="deferred.md"))
        ticket_path = result["path"]

        # Set completes_issue: false — issue spans future sprints
        fm = read_frontmatter(ticket_path)
        fm["completes_issue"] = False
        write_frontmatter(ticket_path, fm)

        # Move ticket to done (issue stays in sprint issues/ because deferred)
        update_ticket_status(ticket_path, "done")
        move_ticket_to_done(ticket_path)

        sprint_dir = self._sprint_dir(work_dir, "001")
        sprint_issues = sprint_dir / "issues"
        assert (sprint_issues / "deferred.md").exists(), (
            "Issue must still be in sprint issues/ (deferred, not completed)"
        )

        mock_run.side_effect = list(_FULL_CLOSE_SUBPROCESS_SIDE_EFFECTS)
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))

        assert result.get("status") == "success", (
            f"Expected status: success for deferred issue, got: {result}"
        )
        # Deferred issue must NOT appear in unresolved_issues
        assert "deferred.md" not in result.get("unresolved_issues", []), (
            f"Deferred issue must not be in unresolved_issues: {result}"
        )
