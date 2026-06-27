"""Unit tests for issue three-state lifecycle (pending -> in-progress -> done).

Tests the interactions between create_ticket, move_ticket_to_done, list_issues,
and close_sprint regarding the issue in-progress directory.
"""

import json
from pathlib import Path

import pytest

from clasi.tools.artifact_tools import (
    close_sprint,
    create_sprint,
    create_ticket,
    list_issues,
    move_ticket_to_done,
)
from clasi.frontmatter import read_frontmatter, write_frontmatter
from clasi.mcp_server import set_project
from clasi.state_db import (
    acquire_lock,
    advance_phase,
    record_gate,
)


def _advance_to_ticketing(work_dir, sprint_id: str) -> None:
    """Advance a sprint through review gates to ticketing phase."""
    db_path = work_dir / ".clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # roadmap -> planning-docs
    advance_phase(db_path, sprint_id)  # planning-docs -> architecture-review
    record_gate(db_path, sprint_id, "architecture_review", "passed")
    advance_phase(db_path, sprint_id)  # architecture-review -> stakeholder-review
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")
    advance_phase(db_path, sprint_id)  # stakeholder-review -> ticketing


def _advance_to_executing(work_dir, sprint_id: str) -> None:
    """Advance a sprint through to executing phase."""
    _advance_to_ticketing(work_dir, sprint_id)
    db_path = work_dir / ".clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # ticketing -> executing
    acquire_lock(db_path, sprint_id)


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


def _sprint_issues_dir(work_dir, sprint_id: str = "001") -> "Path":
    """Return the sprint-scoped issues directory for a sprint."""
    from pathlib import Path
    sprints_dir = work_dir / ".clasi" / "sprints"
    for d in sorted(sprints_dir.iterdir()):
        if d.is_dir() and d.name.startswith(sprint_id + "-"):
            return d / "issues"
    raise ValueError(f"Sprint dir for {sprint_id!r} not found in {sprints_dir}")


def _setup_sprint_with_issue(work_dir, issue_content="---\nstatus: pending\n---\n\n# My Idea\n"):
    """Create a sprint in ticketing phase with an issue file in the pending pool."""
    create_sprint("Test Sprint")
    _advance_to_ticketing(work_dir, "001")
    pending = work_dir / ".clasi" / "issues"
    pending.mkdir(parents=True, exist_ok=True)
    (pending / "my-idea.md").write_text(issue_content)
    return pending


class TestCreateTicketMovesToInProgress:
    """create_ticket should move referenced issues to the sprint issues dir."""

    def test_moves_issue_from_pending_to_in_progress(self, work_dir):
        pending = _setup_sprint_with_issue(work_dir)

        create_ticket("001", "Implement Idea", issue="my-idea.md")

        sprint_issues = _sprint_issues_dir(work_dir, "001")
        # Issue should be in sprint issues dir, not in pending
        assert not (pending / "my-idea.md").exists()
        assert (sprint_issues / "my-idea.md").exists()

    def test_updates_frontmatter_with_sprint_and_ticket(self, work_dir):
        pending = _setup_sprint_with_issue(work_dir)

        create_ticket("001", "Implement Idea", issue="my-idea.md")

        sprint_issues = _sprint_issues_dir(work_dir, "001")
        fm = read_frontmatter(sprint_issues / "my-idea.md")
        assert fm["status"] == "in-progress"
        assert fm["sprint"] == "001"
        assert "001-001" in fm["tickets"]

    def test_appends_ticket_when_issue_already_in_progress(self, work_dir):
        pending = _setup_sprint_with_issue(work_dir)

        create_ticket("001", "Part 1", issue="my-idea.md")
        create_ticket("001", "Part 2", issue="my-idea.md")

        sprint_issues = _sprint_issues_dir(work_dir, "001")
        # Should still be in sprint issues dir (not moved again)
        assert (sprint_issues / "my-idea.md").exists()
        assert not (pending / "my-idea.md").exists()

        fm = read_frontmatter(sprint_issues / "my-idea.md")
        assert fm["tickets"] == ["001-001", "001-002"]

    def test_creates_in_progress_directory(self, work_dir):
        _setup_sprint_with_issue(work_dir)

        create_ticket("001", "Task", issue="my-idea.md")

        sprint_issues = _sprint_issues_dir(work_dir, "001")
        assert sprint_issues.is_dir()


class TestMoveTicketToDoneTriggersCompletion:
    """move_ticket_to_done should move issues to done/ when all tickets complete."""

    def test_moves_issue_to_done_when_single_ticket_done(self, work_dir):
        _setup_sprint_with_issue(work_dir)

        result = json.loads(create_ticket("001", "Implement Idea", issue="my-idea.md"))
        ticket_path = result["path"]

        # Set ticket status to done
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)

        # Move ticket to done
        move_result = json.loads(move_ticket_to_done(ticket_path))

        # Issue should now be in sprint issues/done/ dir with status=done
        sprint_issues = _sprint_issues_dir(work_dir, "001")
        assert not (sprint_issues / "my-idea.md").exists()
        assert (sprint_issues / "done" / "my-idea.md").exists()

        # Check issue frontmatter
        issue_fm = read_frontmatter(sprint_issues / "done" / "my-idea.md")
        assert issue_fm["status"] == "done"

        # Result should report completed issue
        assert "completed_issues" in move_result
        assert "my-idea.md" in move_result["completed_issues"]

    def test_leaves_issue_in_progress_when_some_tickets_open(self, work_dir):
        _setup_sprint_with_issue(work_dir)

        result1 = json.loads(create_ticket("001", "Part 1", issue="my-idea.md"))
        json.loads(create_ticket("001", "Part 2", issue="my-idea.md"))

        # Only complete ticket 1
        ticket1_path = result1["path"]
        fm1 = read_frontmatter(ticket1_path)
        fm1["status"] = "done"
        write_frontmatter(ticket1_path, fm1)
        move_result = json.loads(move_ticket_to_done(ticket1_path))

        # Issue should still be in sprint issues dir (ticket 2 is not done)
        sprint_issues = _sprint_issues_dir(work_dir, "001")
        assert (sprint_issues / "my-idea.md").exists()
        assert not (sprint_issues / "done" / "my-idea.md").exists()
        assert "completed_issues" not in move_result

    def test_moves_issue_when_last_ticket_completes(self, work_dir):
        _setup_sprint_with_issue(work_dir)

        result1 = json.loads(create_ticket("001", "Part 1", issue="my-idea.md"))
        result2 = json.loads(create_ticket("001", "Part 2", issue="my-idea.md"))

        # Complete ticket 1
        ticket1_path = result1["path"]
        fm1 = read_frontmatter(ticket1_path)
        fm1["status"] = "done"
        write_frontmatter(ticket1_path, fm1)
        move_ticket_to_done(ticket1_path)

        # Complete ticket 2
        ticket2_path = result2["path"]
        fm2 = read_frontmatter(ticket2_path)
        fm2["status"] = "done"
        write_frontmatter(ticket2_path, fm2)
        move_result = json.loads(move_ticket_to_done(ticket2_path))

        # Now issue should have moved to sprint issues/done/ dir
        sprint_issues = _sprint_issues_dir(work_dir, "001")
        assert not (sprint_issues / "my-idea.md").exists()
        assert (sprint_issues / "done" / "my-idea.md").exists()
        issue_fm = read_frontmatter(sprint_issues / "done" / "my-idea.md")
        assert issue_fm["status"] == "done"
        assert "completed_issues" in move_result

    def test_ticket_without_issue_ref_works_normally(self, work_dir):
        create_sprint("Test Sprint")
        _advance_to_ticketing(work_dir, "001")

        result = json.loads(create_ticket("001", "No issue ref"))
        ticket_path = result["path"]

        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)

        move_result = json.loads(move_ticket_to_done(ticket_path))
        assert "completed_issues" not in move_result

    def test_completed_issues_absent_when_issue_not_complete(self, work_dir):
        """completed_issues key is absent when the issue is not yet fully done."""
        _setup_sprint_with_issue(work_dir)

        result1 = json.loads(create_ticket("001", "Part 1", issue="my-idea.md"))
        json.loads(create_ticket("001", "Part 2", issue="my-idea.md"))

        ticket1_path = result1["path"]
        fm1 = read_frontmatter(ticket1_path)
        fm1["status"] = "done"
        write_frontmatter(ticket1_path, fm1)
        move_result = json.loads(move_ticket_to_done(ticket1_path))

        assert "completed_issues" not in move_result

    def test_completes_issue_false_suppresses_completion(self, work_dir):
        """completes_issue: false on moving ticket suppresses auto-completion."""
        _setup_sprint_with_issue(work_dir)

        result = json.loads(create_ticket("001", "Task", issue="my-idea.md"))
        ticket_path = result["path"]

        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        fm["completes_issue"] = {"my-idea.md": False}
        write_frontmatter(ticket_path, fm)

        move_result = json.loads(move_ticket_to_done(ticket_path))

        # Issue should NOT be completed due to the suppression flag
        sprint_issues = _sprint_issues_dir(work_dir, "001")
        assert (sprint_issues / "my-idea.md").exists()
        assert not (sprint_issues / "done" / "my-idea.md").exists()
        assert "completed_issues" not in move_result


class TestSprint001Scenario:
    """Sprint 001 post-mortem scenario: T1 has issue: ref, T2-T4 do not.

    After moving T4 to done (the last ticket), the issue should auto-complete
    even though T4 has no issue: ref — because _sweep_done_issues is unconditional.
    """

    def test_issue_completes_when_last_ticket_has_no_issue_ref(self, work_dir):
        """Issue auto-completes via T4 even though T4 carries no issue: ref."""
        # Set up: create sprint with one issue in pending pool
        create_sprint("Sprint 001 Scenario")
        _advance_to_ticketing(work_dir, "001")
        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "feature.md").write_text(
            "---\nstatus: pending\n---\n\n# Feature\n", encoding="utf-8"
        )

        # T1: created with issue: ref — moves feature.md to sprint issues dir
        r1 = json.loads(create_ticket("001", "T1 with ref", issue="feature.md"))
        t1_path = r1["path"]

        # T2, T3, T4: created without issue ref (simulates sprint 001 scenario)
        r2 = json.loads(create_ticket("001", "T2 no ref"))
        r3 = json.loads(create_ticket("001", "T3 no ref"))
        r4 = json.loads(create_ticket("001", "T4 no ref"))

        # But the issue's tickets list must include T2-T4 for the sweep to work.
        # Manually add T2-T4 refs to the issue's tickets frontmatter.
        sprint_issues = _sprint_issues_dir(work_dir, "001")
        issue_fm = read_frontmatter(sprint_issues / "feature.md")
        issue_fm["tickets"] = ["001-001", "001-002", "001-003", "001-004"]
        write_frontmatter(sprint_issues / "feature.md", issue_fm)

        # Complete T1 through T3
        for r in [r1, r2, r3]:
            fm = read_frontmatter(r["path"])
            fm["status"] = "done"
            write_frontmatter(r["path"], fm)
            move_ticket_to_done(r["path"])

        # Issue should still be in-progress (T4 not done)
        assert (sprint_issues / "feature.md").exists()
        assert not (sprint_issues / "done" / "feature.md").exists()

        # Complete T4 (no issue: ref) — this should trigger auto-completion
        fm4 = read_frontmatter(r4["path"])
        fm4["status"] = "done"
        write_frontmatter(r4["path"], fm4)
        move_result = json.loads(move_ticket_to_done(r4["path"]))

        # Issue must now be in done/ even though T4 had no issue: ref
        assert not (sprint_issues / "feature.md").exists(), (
            "Issue must not remain in sprint issues/ after all tickets done"
        )
        assert (sprint_issues / "done" / "feature.md").exists(), (
            "Issue must be in sprint issues/done/ after all tickets done"
        )
        done_fm = read_frontmatter(sprint_issues / "done" / "feature.md")
        assert done_fm["status"] == "done"

        assert "completed_issues" in move_result
        assert "feature.md" in move_result["completed_issues"]


class TestListIssuesPendingPool:
    """list_issues returns only the pending pool (.clasi/issues/*.md)."""

    def test_lists_pending_issues(self, work_dir):
        """list_issues returns pending issues from the pending pool."""
        issues_dir = work_dir / ".clasi" / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        (issues_dir / "pending.md").write_text("---\nstatus: pending\n---\n\n# Pending\n")

        result = json.loads(list_issues())
        assert len(result) == 1

        pending = next(r for r in result if r["filename"] == "pending.md")
        assert pending["status"] == "pending"

    def test_excludes_done(self, work_dir):
        """list_issues excludes files in subdirectories (done/, in-progress/)."""
        issues_dir = work_dir / ".clasi" / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        (issues_dir / "active.md").write_text("# Active\n")
        done = issues_dir / "done"
        done.mkdir()
        (done / "finished.md").write_text("# Finished\n")

        result = json.loads(list_issues())
        filenames = [r["filename"] for r in result]
        assert "active.md" in filenames
        assert "finished.md" not in filenames


class TestCloseSprintDoesNotBulkMove:
    """close_sprint should NOT bulk-move issues; it should verify they are resolved."""

    def test_close_sprint_succeeds_when_issues_already_done(self, work_dir):
        """Issues marked done by ticket completion should not block close."""
        _setup_sprint_with_issue(work_dir)

        result = json.loads(create_ticket("001", "Task", issue="my-idea.md"))
        ticket_path = result["path"]

        # Complete the ticket and move it to done (which triggers issue completion)
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)
        move_ticket_to_done(ticket_path)

        # Verify issue has status=done in sprint issues/done/ dir (file moved)
        sprint_issues = _sprint_issues_dir(work_dir, "001")
        assert not (sprint_issues / "my-idea.md").exists()
        assert (sprint_issues / "done" / "my-idea.md").exists()
        issue_fm = read_frontmatter(sprint_issues / "done" / "my-idea.md")
        assert issue_fm["status"] == "done"

        # Close sprint should succeed
        close_result = json.loads(close_sprint("001"))
        # Should not have moved_issues (they were already handled by ticket completion)
        assert "moved_issues" not in close_result

    def test_close_sprint_no_bulk_move_of_in_progress_issues(self, work_dir):
        """In-progress issues should NOT be bulk-moved at sprint close."""
        _setup_sprint_with_issue(work_dir)

        create_ticket("001", "Task", issue="my-idea.md")

        # Don't complete the ticket -- issue stays in sprint issues dir
        sprint_issues = _sprint_issues_dir(work_dir, "001")
        assert (sprint_issues / "my-idea.md").exists()

        # Close sprint (legacy mode) -- should still succeed but report unresolved
        close_result = json.loads(close_sprint("001"))

        # The issue is in-progress and unresolved — it should be reported
        assert "unresolved_issues" in close_result

    def test_close_without_issues(self, work_dir):
        """Sprint with no issues closes cleanly."""
        create_sprint("Sprint")
        result = json.loads(close_sprint("001"))
        assert "unresolved_issues" not in result


# ---------------------------------------------------------------------------
# Full sprint-scoped issue lifecycle integration tests
# ---------------------------------------------------------------------------


def _find_sprint_dir(work_dir, sprint_id: str = "001"):
    """Return the active sprint directory for sprint_id."""
    sprints_dir = work_dir / ".clasi" / "sprints"
    for d in sorted(sprints_dir.iterdir()):
        if d.is_dir() and d.name.startswith(sprint_id + "-"):
            return d
    raise ValueError(f"Sprint dir for {sprint_id!r} not found in {sprints_dir}")


def _find_done_sprint_dir(work_dir, sprint_id: str = "001"):
    """Return the archived sprint directory for sprint_id."""
    done_dir = work_dir / ".clasi" / "sprints" / "done"
    for d in sorted(done_dir.iterdir()):
        if d.is_dir() and d.name.startswith(sprint_id + "-"):
            return d
    raise ValueError(f"Done sprint dir for {sprint_id!r} not found in {done_dir}")


class TestSprintScopedIssueLifecycle:
    """End-to-end lifecycle: pending issue → sprint claim → done → archive.

    Exercises the complete sprint-scoped issue lifecycle:
    1. Create issue in .clasi/issues/ (pending pool).
    2. Create a sprint, advance to ticketing.
    3. Claim the issue via create_ticket → file moves to <sprint>/issues/.
    4. Complete the ticket via move_ticket_to_done → issue frontmatter status=done.
    5. Archive the sprint via close_sprint → issue at done/<sprint>/issues/.
    """

    def test_full_lifecycle(self, work_dir):
        """Full sprint-scoped issue lifecycle passes end-to-end."""
        # Step 1: Create a pending issue in the pending pool
        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        issue_file = pending_pool / "my-idea.md"
        issue_file.write_text(
            "---\nstatus: open\n---\n\n# My Idea\n\nDetails here.\n",
            encoding="utf-8",
        )
        assert issue_file.exists(), "Issue must exist in pending pool before claim"

        # Step 2: Create a sprint and advance to ticketing
        create_sprint("Lifecycle Sprint")
        _advance_to_ticketing(work_dir, "001")
        sprint_dir = _find_sprint_dir(work_dir, "001")
        sprint_issues_dir = sprint_dir / "issues"

        # Step 3: Claim the issue via create_ticket
        result = json.loads(
            create_ticket("001", "Implement My Idea", issue="my-idea.md")
        )
        ticket_path = result["path"]

        # Issue is now at <sprint>/issues/, not in the pending pool
        assert not issue_file.exists(), (
            "Issue must not remain in pending pool after being claimed"
        )
        sprint_issue_path = sprint_issues_dir / "my-idea.md"
        assert sprint_issue_path.exists(), (
            "Issue must be in sprint issues dir after create_ticket"
        )
        issue_fm = read_frontmatter(sprint_issue_path)
        assert issue_fm["status"] == "in-progress"
        assert issue_fm["sprint"] == "001"
        assert "001-001" in issue_fm["tickets"]

        # Step 4: Complete the ticket and call move_ticket_to_done
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)
        move_result = json.loads(move_ticket_to_done(ticket_path))

        # Issue is moved to <sprint>/issues/done/ with status=done
        assert "completed_issues" in move_result
        assert "my-idea.md" in move_result["completed_issues"]
        done_issue_path_in_sprint = sprint_issues_dir / "done" / "my-idea.md"
        assert done_issue_path_in_sprint.exists(), (
            "Issue file must be at sprint issues/done/ after ticket completion"
        )
        assert not sprint_issue_path.exists(), (
            "Issue file must not remain at sprint issues/ (it was moved to done/)"
        )
        done_fm = read_frontmatter(done_issue_path_in_sprint)
        assert done_fm["status"] == "done"

        # Verify project.get_issue resolves the issue from issues/done/
        from clasi.project import Project
        proj = Project(work_dir)
        resolved_issue = proj.get_issue("my-idea.md")
        assert resolved_issue.path.parent.name == "done"
        assert resolved_issue.status == "done"

        # Step 5: Archive the sprint
        close_result = json.loads(close_sprint("001"))
        assert "new_path" in close_result
        assert "done" in close_result["new_path"]
        assert not sprint_dir.exists(), "Original sprint dir must be gone after archive"

        # Issue is now at done/<sprint>/issues/done/
        done_sprint_dir = _find_done_sprint_dir(work_dir, "001")
        done_issue_path = done_sprint_dir / "issues" / "done" / "my-idea.md"
        assert done_issue_path.exists(), (
            "Issue must be at done/<sprint>/issues/done/ after sprint archive"
        )
        archived_fm = read_frontmatter(done_issue_path)
        assert archived_fm["status"] == "done"

    def test_archive_carries_issue_to_done_dir(self, work_dir):
        """close_sprint carries the issues/done/ directory to done/<sprint>/issues/done/."""
        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "story.md").write_text(
            "---\nstatus: open\n---\n\n# Story\n", encoding="utf-8"
        )

        create_sprint("Story Sprint")
        _advance_to_ticketing(work_dir, "001")

        result = json.loads(create_ticket("001", "Story Task", issue="story.md"))
        ticket_path = result["path"]

        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)
        move_ticket_to_done(ticket_path)

        close_sprint("001")

        done_sprint_dir = _find_done_sprint_dir(work_dir, "001")
        assert (done_sprint_dir / "issues" / "done" / "story.md").exists(), (
            "Archived issue must be under done/<sprint>/issues/done/"
        )

    def test_multiple_issues_all_archived(self, work_dir):
        """Multiple sprint-scoped issues all appear at done/<sprint>/issues/done/."""
        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        for name in ["alpha.md", "beta.md", "gamma.md"]:
            (pending_pool / name).write_text(
                f"---\nstatus: open\n---\n\n# {name}\n", encoding="utf-8"
            )

        create_sprint("Multi Sprint")
        _advance_to_ticketing(work_dir, "001")

        for name in ["alpha.md", "beta.md", "gamma.md"]:
            r = json.loads(create_ticket("001", f"Task {name}", issue=name))
            fm = read_frontmatter(r["path"])
            fm["status"] = "done"
            write_frontmatter(r["path"], fm)
            move_ticket_to_done(r["path"])

        close_sprint("001")

        done_sprint_dir = _find_done_sprint_dir(work_dir, "001")
        for name in ["alpha.md", "beta.md", "gamma.md"]:
            assert (done_sprint_dir / "issues" / "done" / name).exists(), (
                f"{name} must be at done/<sprint>/issues/done/ after archive"
            )


class TestSprintIssuesDirUnit:
    """Unit tests for Sprint.issues_dir and Sprint.list_issues()."""

    def test_issues_dir_returns_sprint_subpath(self, work_dir):
        """Sprint.issues_dir returns <sprint_path>/issues."""
        from clasi.project import Project

        create_sprint("Test Sprint")
        proj = Project(work_dir)
        sprint = proj.get_sprint("001")
        assert sprint.issues_dir == sprint.path / "issues"

    def test_issues_dir_is_path_object(self, work_dir):
        """Sprint.issues_dir returns a Path (not a string)."""
        from pathlib import Path
        from clasi.project import Project

        create_sprint("Test Sprint")
        proj = Project(work_dir)
        sprint = proj.get_sprint("001")
        assert isinstance(sprint.issues_dir, Path)

    def test_list_issues_empty_when_no_dir(self, work_dir):
        """Sprint.list_issues() returns [] when issues/ does not exist."""
        from clasi.project import Project

        create_sprint("Test Sprint")
        proj = Project(work_dir)
        sprint = proj.get_sprint("001")
        assert not sprint.issues_dir.exists()
        assert sprint.list_issues() == []

    def test_list_issues_returns_issue_objects(self, work_dir):
        """Sprint.list_issues() returns Issue instances for each .md file."""
        from clasi.issue import Issue
        from clasi.project import Project

        create_sprint("Test Sprint")
        _advance_to_ticketing(work_dir, "001")

        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "feature.md").write_text(
            "---\nstatus: open\n---\n\n# Feature\n", encoding="utf-8"
        )

        create_ticket("001", "Implement Feature", issue="feature.md")

        proj = Project(work_dir)
        sprint = proj.get_sprint("001")
        issues = sprint.list_issues()
        assert len(issues) == 1
        assert isinstance(issues[0], Issue)
        assert issues[0].path.name == "feature.md"

    def test_list_issues_multiple(self, work_dir):
        """Sprint.list_issues() returns all .md issues sorted by name."""
        from clasi.project import Project

        create_sprint("Test Sprint")
        _advance_to_ticketing(work_dir, "001")

        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        for name in ["aaa.md", "bbb.md", "ccc.md"]:
            (pending_pool / name).write_text(
                f"---\nstatus: open\n---\n\n# {name}\n", encoding="utf-8"
            )
            create_ticket("001", f"Task {name}", issue=name)

        proj = Project(work_dir)
        sprint = proj.get_sprint("001")
        issues = sprint.list_issues()
        assert len(issues) == 3
        assert [i.path.name for i in issues] == ["aaa.md", "bbb.md", "ccc.md"]


# ---------------------------------------------------------------------------
# Auto-link field fix tests (Sprint 014 ticket 003, A1)
# ---------------------------------------------------------------------------


class TestCreateTicketAutoLinkField:
    """create_ticket auto-link reads issues: field first, falls back to todos:.

    Tests for the Sprint 014 fix: the auto-link block in create_ticket was
    reading sprint frontmatter's todos: field, but link_sprint_issues writes
    issues: instead. The fix reads issues: first and falls back to todos: for
    legacy sprint compatibility.
    """

    def _find_sprint_dir(self, work_dir, sprint_id: str = "001") -> Path:
        sprints_dir = work_dir / ".clasi" / "sprints"
        for d in sorted(sprints_dir.iterdir()):
            if d.is_dir() and d.name.startswith(sprint_id + "-"):
                return d
        raise ValueError(f"Sprint dir for {sprint_id!r} not found")

    def test_auto_link_reads_issues_field(self, work_dir):
        """create_ticket with no issue= argument auto-links when sprint has issues: field.

        When the sprint frontmatter has issues: [filename] (as written by
        link_sprint_issues), calling create_ticket without an explicit issue=
        argument should auto-link the ticket to that issue filename.
        """
        create_sprint("Auto-Link Sprint")
        _advance_to_ticketing(work_dir, "001")

        # Create an issue in the pending pool
        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "linked-idea.md").write_text(
            "---\nstatus: pending\n---\n\n# Linked Idea\n", encoding="utf-8"
        )

        # Write issues: [filename] directly to sprint frontmatter (simulating
        # what link_sprint_issues would write)
        sprint_dir = self._find_sprint_dir(work_dir, "001")
        sprint_doc = sprint_dir / "sprint.md"
        fm = read_frontmatter(sprint_doc)
        fm["issues"] = ["linked-idea.md"]
        write_frontmatter(sprint_doc, fm)

        # Call create_ticket without issue= — auto-link should fire via issues: field
        result = json.loads(create_ticket("001", "Implement Linked Idea"))

        ticket_path = result["path"]
        ticket_fm = read_frontmatter(ticket_path)

        # Ticket must have issue: set from the auto-link
        assert ticket_fm.get("issue") == "linked-idea.md", (
            f"Expected ticket issue: 'linked-idea.md', got: {ticket_fm.get('issue')!r}"
        )

        # Issue must have been moved to sprint issues dir with status in-progress
        sprint_issues_dir = sprint_dir / "issues"
        assert (sprint_issues_dir / "linked-idea.md").exists(), (
            "Issue must be in sprint issues dir after auto-link"
        )
        issue_fm = read_frontmatter(sprint_issues_dir / "linked-idea.md")
        assert issue_fm["status"] == "in-progress"

    def test_auto_link_falls_back_to_todos_field(self, work_dir):
        """create_ticket auto-link uses todos: as fallback when issues: is absent.

        Legacy sprints may have todos: in their frontmatter. When issues: is
        absent (or empty), the auto-link should fall back to todos: to preserve
        backward compatibility.
        """
        create_sprint("Legacy Auto-Link Sprint")
        _advance_to_ticketing(work_dir, "001")

        # Create an issue in the pending pool
        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "legacy-idea.md").write_text(
            "---\nstatus: pending\n---\n\n# Legacy Idea\n", encoding="utf-8"
        )

        # Write ONLY todos: to sprint frontmatter (legacy sprint format, no issues:)
        sprint_dir = self._find_sprint_dir(work_dir, "001")
        sprint_doc = sprint_dir / "sprint.md"
        fm = read_frontmatter(sprint_doc)
        # Ensure issues: is absent or empty, and todos: is set
        fm.pop("issues", None)
        fm["todos"] = ["legacy-idea.md"]
        write_frontmatter(sprint_doc, fm)

        # Call create_ticket without issue= — auto-link should fire via todos: fallback
        result = json.loads(create_ticket("001", "Implement Legacy Idea"))

        ticket_path = result["path"]
        ticket_fm = read_frontmatter(ticket_path)

        # Ticket must have issue: set from the todos: fallback
        assert ticket_fm.get("issue") == "legacy-idea.md", (
            f"Expected ticket issue: 'legacy-idea.md', got: {ticket_fm.get('issue')!r}"
        )

        # Issue must have been moved to sprint issues dir
        sprint_issues_dir = sprint_dir / "issues"
        assert (sprint_issues_dir / "legacy-idea.md").exists(), (
            "Issue must be in sprint issues dir after todos: fallback auto-link"
        )
        issue_fm = read_frontmatter(sprint_issues_dir / "legacy-idea.md")
        assert issue_fm["status"] == "in-progress"
