"""Unit tests for TODO three-state lifecycle (pending -> in-progress -> done).

Tests the interactions between create_ticket, move_ticket_to_done, list_issues,
and close_sprint regarding the issue in-progress directory.
"""

import json

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


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
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


def _setup_sprint_with_todo(work_dir, todo_content="---\nstatus: pending\n---\n\n# My Idea\n"):
    """Create a sprint in ticketing phase with a TODO file in the pending pool."""
    create_sprint("Test Sprint")
    _advance_to_ticketing(work_dir, "001")
    todo = work_dir / ".clasi" / "issues"
    todo.mkdir(parents=True, exist_ok=True)
    (todo / "my-idea.md").write_text(todo_content)
    return todo


class TestCreateTicketMovesToInProgress:
    """create_ticket should move referenced TODOs to the sprint issues dir."""

    def test_moves_todo_from_pending_to_in_progress(self, work_dir):
        todo = _setup_sprint_with_todo(work_dir)

        create_ticket("001", "Implement Idea", todo="my-idea.md")

        sprint_issues = _sprint_issues_dir(work_dir, "001")
        # TODO should be in sprint issues dir, not in pending
        assert not (todo / "my-idea.md").exists()
        assert (sprint_issues / "my-idea.md").exists()

    def test_updates_frontmatter_with_sprint_and_ticket(self, work_dir):
        todo = _setup_sprint_with_todo(work_dir)

        create_ticket("001", "Implement Idea", todo="my-idea.md")

        sprint_issues = _sprint_issues_dir(work_dir, "001")
        fm = read_frontmatter(sprint_issues / "my-idea.md")
        assert fm["status"] == "in-progress"
        assert fm["sprint"] == "001"
        assert "001-001" in fm["tickets"]

    def test_appends_ticket_when_todo_already_in_progress(self, work_dir):
        todo = _setup_sprint_with_todo(work_dir)

        create_ticket("001", "Part 1", todo="my-idea.md")
        create_ticket("001", "Part 2", todo="my-idea.md")

        sprint_issues = _sprint_issues_dir(work_dir, "001")
        # Should still be in sprint issues dir (not moved again)
        assert (sprint_issues / "my-idea.md").exists()
        assert not (todo / "my-idea.md").exists()

        fm = read_frontmatter(sprint_issues / "my-idea.md")
        assert fm["tickets"] == ["001-001", "001-002"]

    def test_creates_in_progress_directory(self, work_dir):
        todo = _setup_sprint_with_todo(work_dir)

        create_ticket("001", "Task", todo="my-idea.md")

        sprint_issues = _sprint_issues_dir(work_dir, "001")
        assert sprint_issues.is_dir()


class TestMoveTicketToDoneTriggersCompletion:
    """move_ticket_to_done should move TODOs to done/ when all tickets complete."""

    def test_moves_todo_to_done_when_single_ticket_done(self, work_dir):
        todo = _setup_sprint_with_todo(work_dir)

        result = json.loads(create_ticket("001", "Implement Idea", todo="my-idea.md"))
        ticket_path = result["path"]

        # Set ticket status to done
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)

        # Move ticket to done
        move_result = json.loads(move_ticket_to_done(ticket_path))

        # TODO should remain in sprint issues dir with status=done (no file move)
        sprint_issues = _sprint_issues_dir(work_dir, "001")
        assert (sprint_issues / "my-idea.md").exists()
        assert not (todo / "done" / "my-idea.md").exists()

        # Check TODO frontmatter
        todo_fm = read_frontmatter(sprint_issues / "my-idea.md")
        assert todo_fm["status"] == "done"

        # Result should report completed TODO
        assert "completed_todos" in move_result
        assert "my-idea.md" in move_result["completed_todos"]

    def test_leaves_todo_in_progress_when_some_tickets_open(self, work_dir):
        todo = _setup_sprint_with_todo(work_dir)

        result1 = json.loads(create_ticket("001", "Part 1", todo="my-idea.md"))
        result2 = json.loads(create_ticket("001", "Part 2", todo="my-idea.md"))

        # Only complete ticket 1
        ticket1_path = result1["path"]
        fm1 = read_frontmatter(ticket1_path)
        fm1["status"] = "done"
        write_frontmatter(ticket1_path, fm1)
        move_result = json.loads(move_ticket_to_done(ticket1_path))

        # TODO should still be in sprint issues dir (ticket 2 is not done)
        sprint_issues = _sprint_issues_dir(work_dir, "001")
        assert (sprint_issues / "my-idea.md").exists()
        assert not (todo / "done" / "my-idea.md").exists()
        assert "completed_todos" not in move_result

    def test_moves_todo_when_last_ticket_completes(self, work_dir):
        todo = _setup_sprint_with_todo(work_dir)

        result1 = json.loads(create_ticket("001", "Part 1", todo="my-idea.md"))
        result2 = json.loads(create_ticket("001", "Part 2", todo="my-idea.md"))

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

        # Now TODO should have status=done in sprint issues dir (no file move)
        sprint_issues = _sprint_issues_dir(work_dir, "001")
        assert (sprint_issues / "my-idea.md").exists()
        assert not (todo / "done" / "my-idea.md").exists()
        todo_fm = read_frontmatter(sprint_issues / "my-idea.md")
        assert todo_fm["status"] == "done"
        assert "completed_todos" in move_result

    def test_ticket_without_todo_ref_works_normally(self, work_dir):
        create_sprint("Test Sprint")
        _advance_to_ticketing(work_dir, "001")

        result = json.loads(create_ticket("001", "No TODO ref"))
        ticket_path = result["path"]

        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)

        move_result = json.loads(move_ticket_to_done(ticket_path))
        assert "completed_todos" not in move_result


class TestListIssuesPendingPool:
    """list_issues returns only the pending pool (.clasi/issues/*.md)."""

    def test_lists_pending_issues(self, work_dir):
        """list_issues returns pending issues from the pending pool."""
        todo = work_dir / ".clasi" / "issues"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "pending.md").write_text("---\nstatus: pending\n---\n\n# Pending\n")

        result = json.loads(list_issues())
        assert len(result) == 1

        pending = next(r for r in result if r["filename"] == "pending.md")
        assert pending["status"] == "pending"

    def test_excludes_done(self, work_dir):
        """list_issues excludes files in subdirectories (done/, in-progress/)."""
        todo = work_dir / ".clasi" / "issues"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "active.md").write_text("# Active\n")
        done = todo / "done"
        done.mkdir()
        (done / "finished.md").write_text("# Finished\n")

        result = json.loads(list_issues())
        filenames = [r["filename"] for r in result]
        assert "active.md" in filenames
        assert "finished.md" not in filenames


class TestCloseSprintDoesNotBulkMove:
    """close_sprint should NOT bulk-move TODOs; it should verify they are resolved."""

    def test_close_sprint_succeeds_when_todos_already_done(self, work_dir):
        """TODOs marked done by ticket completion should not block close."""
        todo = _setup_sprint_with_todo(work_dir)

        result = json.loads(create_ticket("001", "Task", todo="my-idea.md"))
        ticket_path = result["path"]

        # Complete the ticket and move it to done (which triggers TODO completion)
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)
        move_ticket_to_done(ticket_path)

        # Verify TODO has status=done in sprint issues dir (no file move)
        sprint_issues = _sprint_issues_dir(work_dir, "001")
        assert (sprint_issues / "my-idea.md").exists()
        todo_fm = read_frontmatter(sprint_issues / "my-idea.md")
        assert todo_fm["status"] == "done"

        # Close sprint should succeed
        close_result = json.loads(close_sprint("001"))
        # Should not have moved_todos (they were already handled by ticket completion)
        assert "moved_todos" not in close_result

    def test_close_sprint_no_bulk_move_of_in_progress_todos(self, work_dir):
        """In-progress TODOs should NOT be bulk-moved at sprint close."""
        todo = _setup_sprint_with_todo(work_dir)

        create_ticket("001", "Task", todo="my-idea.md")

        # Don't complete the ticket -- TODO stays in sprint issues dir
        sprint_issues = _sprint_issues_dir(work_dir, "001")
        assert (sprint_issues / "my-idea.md").exists()

        # Close sprint (legacy mode) -- should still succeed but report unresolved
        close_result = json.loads(close_sprint("001"))

        # The TODO should NOT have been moved to done/ by close_sprint
        # (it may still exist in sprint issues dir since close doesn't bulk-move)
        assert "unresolved_todos" in close_result or not (todo / "done" / "my-idea.md").exists()

    def test_close_without_todos(self, work_dir):
        """Sprint with no TODOs closes cleanly."""
        create_sprint("Sprint")
        result = json.loads(close_sprint("001"))
        assert "unresolved_todos" not in result


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
            create_ticket("001", "Implement My Idea", todo="my-idea.md")
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

        # Issue frontmatter shows done; file remains at <sprint>/issues/
        assert "completed_todos" in move_result
        assert "my-idea.md" in move_result["completed_todos"]
        assert sprint_issue_path.exists(), (
            "Issue file must remain at sprint issues dir (frontmatter-only update)"
        )
        done_fm = read_frontmatter(sprint_issue_path)
        assert done_fm["status"] == "done"

        # Step 5: Archive the sprint
        close_result = json.loads(close_sprint("001"))
        assert "new_path" in close_result
        assert "done" in close_result["new_path"]
        assert not sprint_dir.exists(), "Original sprint dir must be gone after archive"

        # Issue is now at done/<sprint>/issues/
        done_sprint_dir = _find_done_sprint_dir(work_dir, "001")
        done_issue_path = done_sprint_dir / "issues" / "my-idea.md"
        assert done_issue_path.exists(), (
            "Issue must be at done/<sprint>/issues/ after sprint archive"
        )
        archived_fm = read_frontmatter(done_issue_path)
        assert archived_fm["status"] == "done"

    def test_archive_carries_issue_to_done_dir(self, work_dir):
        """close_sprint carries the issues/ directory to done/<sprint>/issues/."""
        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "story.md").write_text(
            "---\nstatus: open\n---\n\n# Story\n", encoding="utf-8"
        )

        create_sprint("Story Sprint")
        _advance_to_ticketing(work_dir, "001")
        sprint_dir = _find_sprint_dir(work_dir, "001")

        result = json.loads(create_ticket("001", "Story Task", todo="story.md"))
        ticket_path = result["path"]

        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)
        move_ticket_to_done(ticket_path)

        close_sprint("001")

        done_sprint_dir = _find_done_sprint_dir(work_dir, "001")
        assert (done_sprint_dir / "issues" / "story.md").exists(), (
            "Archived issue must be under done/<sprint>/issues/"
        )

    def test_multiple_issues_all_archived(self, work_dir):
        """Multiple sprint-scoped issues all appear at done/<sprint>/issues/."""
        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        for name in ["alpha.md", "beta.md", "gamma.md"]:
            (pending_pool / name).write_text(
                f"---\nstatus: open\n---\n\n# {name}\n", encoding="utf-8"
            )

        create_sprint("Multi Sprint")
        _advance_to_ticketing(work_dir, "001")

        for name in ["alpha.md", "beta.md", "gamma.md"]:
            r = json.loads(create_ticket("001", f"Task {name}", todo=name))
            fm = read_frontmatter(r["path"])
            fm["status"] = "done"
            write_frontmatter(r["path"], fm)
            move_ticket_to_done(r["path"])

        close_sprint("001")

        done_sprint_dir = _find_done_sprint_dir(work_dir, "001")
        for name in ["alpha.md", "beta.md", "gamma.md"]:
            assert (done_sprint_dir / "issues" / name).exists(), (
                f"{name} must be at done/<sprint>/issues/ after archive"
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

        create_ticket("001", "Implement Feature", todo="feature.md")

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
            create_ticket("001", f"Task {name}", todo=name)

        proj = Project(work_dir)
        sprint = proj.get_sprint("001")
        issues = sprint.list_issues()
        assert len(issues) == 3
        assert [i.path.name for i in issues] == ["aaa.md", "bbb.md", "ccc.md"]
