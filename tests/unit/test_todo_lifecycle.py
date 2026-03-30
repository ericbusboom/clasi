"""Unit tests for TODO three-state lifecycle (pending -> in-progress -> done).

Tests the interactions between create_ticket, move_ticket_to_done, list_todos,
and close_sprint regarding the TODO in-progress directory.
"""

import json

import pytest

from claude_agent_skills.artifact_tools import (
    close_sprint,
    create_sprint,
    create_ticket,
    list_todos,
    move_ticket_to_done,
)
from claude_agent_skills.frontmatter import read_frontmatter, write_frontmatter
from claude_agent_skills.mcp_server import set_project
from claude_agent_skills.state_db import (
    acquire_lock,
    advance_phase,
    record_gate,
)


def _advance_to_ticketing(work_dir, sprint_id: str) -> None:
    """Advance a sprint through review gates to ticketing phase."""
    db_path = work_dir / "docs" / "clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # planning-docs -> architecture-review
    record_gate(db_path, sprint_id, "architecture_review", "passed")
    advance_phase(db_path, sprint_id)  # architecture-review -> stakeholder-review
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")
    advance_phase(db_path, sprint_id)  # stakeholder-review -> ticketing


def _advance_to_executing(work_dir, sprint_id: str) -> None:
    """Advance a sprint through to executing phase."""
    _advance_to_ticketing(work_dir, sprint_id)
    db_path = work_dir / "docs" / "clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # ticketing -> executing
    acquire_lock(db_path, sprint_id)


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    set_project(tmp_path)
    return tmp_path


def _setup_sprint_with_todo(work_dir, todo_content="---\nstatus: pending\n---\n\n# My Idea\n"):
    """Create a sprint in ticketing phase with a TODO file."""
    create_sprint("Test Sprint")
    _advance_to_ticketing(work_dir, "001")
    todo = work_dir / "docs" / "clasi" / "todo"
    todo.mkdir(parents=True, exist_ok=True)
    (todo / "my-idea.md").write_text(todo_content)
    return todo


class TestCreateTicketMovesToInProgress:
    """create_ticket should move referenced TODOs to in-progress/."""

    def test_moves_todo_from_pending_to_in_progress(self, work_dir):
        todo = _setup_sprint_with_todo(work_dir)

        create_ticket("001", "Implement Idea", todo="my-idea.md")

        # TODO should be in in-progress/, not in pending
        assert not (todo / "my-idea.md").exists()
        assert (todo / "in-progress" / "my-idea.md").exists()

    def test_updates_frontmatter_with_sprint_and_ticket(self, work_dir):
        todo = _setup_sprint_with_todo(work_dir)

        create_ticket("001", "Implement Idea", todo="my-idea.md")

        fm = read_frontmatter(todo / "in-progress" / "my-idea.md")
        assert fm["status"] == "in-progress"
        assert fm["sprint"] == "001"
        assert "001-001" in fm["tickets"]

    def test_appends_ticket_when_todo_already_in_progress(self, work_dir):
        todo = _setup_sprint_with_todo(work_dir)

        create_ticket("001", "Part 1", todo="my-idea.md")
        create_ticket("001", "Part 2", todo="my-idea.md")

        # Should still be in in-progress/ (not moved again)
        assert (todo / "in-progress" / "my-idea.md").exists()
        assert not (todo / "my-idea.md").exists()

        fm = read_frontmatter(todo / "in-progress" / "my-idea.md")
        assert fm["tickets"] == ["001-001", "001-002"]

    def test_creates_in_progress_directory(self, work_dir):
        todo = _setup_sprint_with_todo(work_dir)
        assert not (todo / "in-progress").exists()

        create_ticket("001", "Task", todo="my-idea.md")

        assert (todo / "in-progress").is_dir()


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

        # TODO should be moved to done/
        assert not (todo / "in-progress" / "my-idea.md").exists()
        assert (todo / "done" / "my-idea.md").exists()

        # Check TODO frontmatter
        todo_fm = read_frontmatter(todo / "done" / "my-idea.md")
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

        # TODO should still be in in-progress/ (ticket 2 is not done)
        assert (todo / "in-progress" / "my-idea.md").exists()
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

        # Now TODO should be in done/
        assert not (todo / "in-progress" / "my-idea.md").exists()
        assert (todo / "done" / "my-idea.md").exists()
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


class TestListTodosIncludesInProgress:
    """list_todos should scan both pending and in-progress directories."""

    def test_lists_pending_and_in_progress(self, work_dir):
        todo = work_dir / "docs" / "clasi" / "todo"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "pending.md").write_text("---\nstatus: pending\n---\n\n# Pending\n")
        in_progress = todo / "in-progress"
        in_progress.mkdir()
        (in_progress / "active.md").write_text(
            "---\nstatus: in-progress\nsprint: '001'\ntickets:\n  - '001-001'\n---\n\n# Active\n"
        )

        result = json.loads(list_todos())
        assert len(result) == 2

        pending = next(r for r in result if r["filename"] == "pending.md")
        active = next(r for r in result if r["filename"] == "active.md")

        assert pending["status"] == "pending"
        assert active["status"] == "in-progress"
        assert active["sprint"] == "001"
        assert active["tickets"] == ["001-001"]

    def test_excludes_done(self, work_dir):
        todo = work_dir / "docs" / "clasi" / "todo"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "active.md").write_text("# Active\n")
        done = todo / "done"
        done.mkdir()
        (done / "finished.md").write_text("# Finished\n")
        in_progress = todo / "in-progress"
        in_progress.mkdir()
        (in_progress / "working.md").write_text("---\nstatus: in-progress\n---\n\n# Working\n")

        result = json.loads(list_todos())
        filenames = [r["filename"] for r in result]
        assert "active.md" in filenames
        assert "working.md" in filenames
        assert "finished.md" not in filenames


class TestCloseSprintDoesNotBulkMove:
    """close_sprint should NOT bulk-move TODOs; it should verify they are resolved."""

    def test_close_sprint_succeeds_when_todos_already_done(self, work_dir):
        """TODOs moved to done/ by ticket completion should not block close."""
        todo = _setup_sprint_with_todo(work_dir)

        result = json.loads(create_ticket("001", "Task", todo="my-idea.md"))
        ticket_path = result["path"]

        # Complete the ticket and move it to done (which triggers TODO completion)
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)
        move_ticket_to_done(ticket_path)

        # Verify TODO is in done/
        assert (todo / "done" / "my-idea.md").exists()

        # Close sprint should succeed
        close_result = json.loads(close_sprint("001"))
        # Should not have moved_todos (they were already moved by ticket completion)
        assert "moved_todos" not in close_result

    def test_close_sprint_no_bulk_move_of_in_progress_todos(self, work_dir):
        """In-progress TODOs should NOT be bulk-moved at sprint close."""
        todo = _setup_sprint_with_todo(work_dir)

        create_ticket("001", "Task", todo="my-idea.md")

        # Don't complete the ticket -- TODO stays in in-progress
        assert (todo / "in-progress" / "my-idea.md").exists()

        # Close sprint (legacy mode) -- should still succeed but report unresolved
        close_result = json.loads(close_sprint("001"))

        # The TODO should NOT have been moved to done/ by close_sprint
        # (it may still exist in in-progress/ since close doesn't bulk-move)
        assert "unresolved_todos" in close_result or not (todo / "done" / "my-idea.md").exists()

    def test_close_without_todos(self, work_dir):
        """Sprint with no TODOs closes cleanly."""
        create_sprint("Sprint")
        result = json.loads(close_sprint("001"))
        assert "unresolved_todos" not in result
