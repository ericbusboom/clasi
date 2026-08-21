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
    link_sprint_issues,
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
    advance_phase(db_path, sprint_id)  # architecture-review -> ticketing (031/002)
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")


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
# Ticket 020-004: issue-linkage instructions actually fire
#
# Root cause: sprint 018 replaced the standalone sprint-roadmap /
# create-tickets skill invocations with a single inline sprint-planner
# agent (src/clasi/plugin/agents/sprint-planner/agent.md +
# create-tickets.md). That agent doc's Roadmap/Detail Mode workflows never
# mentioned link_sprint_issues at all -- the call survived only in the
# now-mostly-orphaned standalone SKILL.md docs and in team-lead's
# non-actionable "Issue Lifecycle Responsibility" appendix, not in any
# numbered workflow step an agent actually executes. create_ticket(issue=)
# and add_issue_ref did get carried into the inline docs, but the one call
# that seeds the sprint-level issues: frontmatter -- link_sprint_issues --
# was dropped. These tests pin the fix: (1) the concrete instruction is
# present in the docs agents actually follow, and (2) the tool chain that
# the fixed instructions now mandate calling, in the order documented,
# produces non-empty sprint issues: and correct per-ticket issue: fields.
# ---------------------------------------------------------------------------


class TestIssueLinkageInstructionsPresent:
    """Static regression guard: the canonical agent docs must instruct
    link_sprint_issues as a concrete, required step -- not just mention it
    in an appendix or an orphaned skill doc nobody's live workflow reads.

    Reads via clasi.project.Project.get_agent(name).definition, the same
    accessor CLASI itself uses to load agent content (clasi/agent.py), so
    this test exercises the real content-loading path rather than a
    hardcoded file path duplicating platform-install logic.
    """

    def _agent_definition(self, name: str) -> str:
        from clasi.project import Project

        # Project() only needs a valid root for path resolution here; the
        # agents directory is packaged, not project-scoped.
        proj = Project(Path.cwd())
        return proj.get_agent(name).definition

    def test_sprint_planner_roadmap_mode_requires_link_sprint_issues(self):
        text = self._agent_definition("sprint-planner")
        roadmap_start = text.index("Roadmap Mode Workflow")
        detail_start = text.index("Detail Mode Workflow")
        roadmap_section = text[roadmap_start:detail_start]
        assert "link_sprint_issues" in roadmap_section, (
            "sprint-planner agent.md's Roadmap Mode Workflow must instruct "
            "link_sprint_issues as a concrete step -- this is the call "
            "agents actually follow when planning a sprint"
        )
        assert "Required" in roadmap_section, (
            "the link_sprint_issues step must be marked required, not "
            "merely mentioned, to survive being skipped as optional"
        )

    def test_sprint_planner_detail_mode_verifies_link_sprint_issues(self):
        text = self._agent_definition("sprint-planner")
        detail_start = text.index("Detail Mode Workflow")
        phase2_start = text.index("Phase 2: Architecture")
        phase1_section = text[detail_start:phase2_start]
        assert "link_sprint_issues" in phase1_section, (
            "sprint-planner agent.md's Detail Mode Phase 1 must verify/call "
            "link_sprint_issues before writing Use Cases or Architecture"
        )

    def test_sprint_planner_create_tickets_doc_verifies_linkage(self):
        # create-tickets.md sits alongside agent.md in the same agent dir;
        # Agent.definition only exposes agent.md, so read this one directly
        # via the same Project._agents_dir the Agent class resolves from.
        from clasi.project import Project

        proj = Project(Path.cwd())
        create_tickets_path = proj._agents_dir / "sprint-planner" / "create-tickets.md"
        assert create_tickets_path.exists(), (
            "sprint-planner/create-tickets.md must exist alongside agent.md"
        )
        text = create_tickets_path.read_text(encoding="utf-8")
        assert "link_sprint_issues" in text, (
            "create-tickets.md must instruct verifying/calling "
            "link_sprint_issues before ticket creation, not just "
            "create_ticket(issue=) and add_issue_ref"
        )
        assert "add_issue_ref" in text, (
            "create-tickets.md must instruct add_issue_ref for tickets "
            "that don't get an issue: back-reference from auto-link"
        )

    def test_team_lead_main_workflow_calls_link_sprint_issues_inline(self):
        text = self._agent_definition("team-lead")
        exec_start = text.index("Execute Issues Through a Sprint")
        add_issue_start = text.index("Add Issue to Existing Sprint")
        exec_section = text[exec_start:add_issue_start]
        assert "link_sprint_issues" in exec_section, (
            "team-lead agent.md's numbered 'Execute Issues Through a "
            "Sprint' workflow must call link_sprint_issues inline, not "
            "only mention it in the separate 'Issue Lifecycle "
            "Responsibility' appendix -- an agent following the numbered "
            "steps literally must hit the call without cross-referencing "
            "a different section"
        )
        # Must appear before sprint-planner is dispatched, not after.
        create_sprint_idx = exec_section.index("create_sprint(title=")
        link_idx = exec_section.index("link_sprint_issues")
        planner_dispatch_idx = exec_section.index("Invoke the sprint-planner agent")
        assert create_sprint_idx < link_idx < planner_dispatch_idx, (
            "link_sprint_issues must be called after create_sprint but "
            "before the sprint-planner dispatch"
        )


class TestDocumentedLinkageSequenceProducesNonEmptyIssues:
    """Behavioral test: script the exact sequence the fixed docs now
    mandate (create_sprint -> link_sprint_issues -> detail_sprint ->
    create_ticket) and assert it produces non-empty sprint.md issues:
    frontmatter and correct per-ticket issue: fields -- the acceptance
    bar from ticket 020-004's third criterion.

    This does not hand-invoke the tools "out of band" in the sense the
    ticket warns against -- it invokes them in the literal order and
    manner the corrected agent docs prescribe (link at roadmap time,
    before any ticket exists; then create tickets per the multi-issue
    rule ticket 020-005 introduced: create_ticket only auto-links when
    the sprint has exactly one linked issue, so a 2+-issue sprint must
    pass issue= explicitly per ticket). A regression that deletes the
    link_sprint_issues call from the docs would not fail this test by
    itself (docs aren't parsed here) -- that is what
    TestIssueLinkageInstructionsPresent guards. This test instead guards
    that *following the documented sequence* still yields the outcome
    the docs promise.
    """

    def test_two_issues_linked_at_roadmap_time_appear_in_sprint_frontmatter(
        self, work_dir
    ):
        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "issue-a.md").write_text(
            "---\nstatus: pending\n---\n\n# Issue A\n", encoding="utf-8"
        )
        (pending_pool / "issue-b.md").write_text(
            "---\nstatus: pending\n---\n\n# Issue B\n", encoding="utf-8"
        )

        # Step matching sprint-planner agent.md Roadmap Mode Workflow
        # steps 1-2: create_sprint, then link_sprint_issues immediately.
        create_sprint("Linked Sprint")
        link_result = json.loads(
            link_sprint_issues("001", ["issue-a.md", "issue-b.md"])
        )
        assert link_result["linked"] == ["issue-a.md", "issue-b.md"]

        sprint_dir = _find_sprint_dir(work_dir, "001")
        sprint_fm = read_frontmatter(sprint_dir / "sprint.md")
        assert sprint_fm.get("issues") == ["issue-a.md", "issue-b.md"], (
            "sprint.md frontmatter issues: must be non-empty and list both "
            "issues after link_sprint_issues, matching the E2E acceptance "
            "bar (sprint.md showed issues: [] before this fix)"
        )

        # Step matching Detail Mode Phase 4: advance to ticketing. Per
        # ticket 020-005, create_ticket only auto-links when the sprint
        # has exactly one linked issue -- with two linked issues here,
        # the docs require passing issue= explicitly per ticket.
        _advance_to_ticketing(work_dir, "001")
        t1 = json.loads(
            create_ticket("001", "Implement Issue A", issue="issue-a.md")
        )
        t2 = json.loads(
            create_ticket("001", "Implement Issue B", issue="issue-b.md")
        )

        t1_fm = read_frontmatter(t1["path"])
        t2_fm = read_frontmatter(t2["path"])

        # Each ticket carries exactly the issue it was created for --
        # never "all sprint issues" (the bug 020-005 fixed).
        assert t1_fm.get("issue") == "issue-a.md", (
            f"ticket 001 issue: field must be 'issue-a.md', got {t1_fm.get('issue')!r}"
        )
        assert t2_fm.get("issue") == "issue-b.md", (
            f"ticket 002 issue: field must be 'issue-b.md', got {t2_fm.get('issue')!r}"
        )

    def test_omitting_issue_on_multi_issue_sprint_leaves_issue_field_empty(
        self, work_dir
    ):
        """create_ticket without issue= on a 2+-issue sprint must NOT
        auto-link -- this is the ticket 020-005 fix itself, exercised via
        the same documented linkage sequence as the test above.
        """
        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "issue-a.md").write_text(
            "---\nstatus: pending\n---\n\n# Issue A\n", encoding="utf-8"
        )
        (pending_pool / "issue-b.md").write_text(
            "---\nstatus: pending\n---\n\n# Issue B\n", encoding="utf-8"
        )

        create_sprint("Linked Sprint")
        link_sprint_issues("001", ["issue-a.md", "issue-b.md"])
        _advance_to_ticketing(work_dir, "001")

        result = json.loads(create_ticket("001", "Unrelated Work"))
        ticket_fm = read_frontmatter(result["path"])
        assert not ticket_fm.get("issue"), (
            "issue: must be empty when issue= is omitted on a multi-issue "
            f"sprint, got {ticket_fm.get('issue')!r}"
        )

        issue_a_fm = read_frontmatter(pending_pool / "issue-a.md")
        issue_b_fm = read_frontmatter(pending_pool / "issue-b.md")
        assert not issue_a_fm.get("tickets")
        assert not issue_b_fm.get("tickets")

    def test_add_issue_ref_backfills_ticket_missing_from_autolink(self, work_dir):
        """When a ticket doesn't get an issue: from auto-link (e.g. it
        targets one specific issue out of several linked to the sprint),
        the documented add_issue_ref repair step must produce a correct
        per-ticket back-reference.
        """
        from clasi.tools.artifact_tools import add_issue_ref

        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "specific-issue.md").write_text(
            "---\nstatus: pending\n---\n\n# Specific Issue\n", encoding="utf-8"
        )

        create_sprint("Backfill Sprint")
        link_sprint_issues("001", ["specific-issue.md"])
        _advance_to_ticketing(work_dir, "001")

        # Ticket created with an explicit, different issue= than what
        # auto-link would apply (simulates a ticket that doesn't cover the
        # sprint's only linked issue and needs a manual add_issue_ref
        # later for a second reference — here we simply verify the tool
        # documented as the repair path establishes the back-reference).
        result = json.loads(create_ticket("001", "Unrelated ticket"))
        ticket_path = result["path"]
        fm_before = read_frontmatter(ticket_path)
        # Auto-link fires here too since only one issue is linked — clear
        # it to simulate the "missing back-reference" case add_issue_ref
        # is documented to repair.
        fm_before.pop("issue", None)
        write_frontmatter(ticket_path, fm_before)

        add_issue_ref(ticket_path, "specific-issue.md")

        fm_after = read_frontmatter(ticket_path)
        assert fm_after.get("issue") == "specific-issue.md", (
            "add_issue_ref must set the ticket's issue: field to the "
            "referenced issue filename"
        )


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
