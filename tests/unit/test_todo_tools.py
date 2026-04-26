"""Unit tests for TODO management MCP tools."""

import json

import pytest

from clasi.tools.artifact_tools import (
    close_sprint,
    create_sprint,
    create_ticket,
    list_todos,
    move_todo_to_done,
)
from clasi.frontmatter import read_frontmatter, write_frontmatter
from clasi.mcp_server import set_project
from clasi.state_db import (
    acquire_lock,
    advance_phase,
    record_gate,
)


@pytest.fixture
def todo_dir(tmp_path, monkeypatch):
    """Set up a temporary working directory with docs/clasi/todo/."""
    monkeypatch.chdir(tmp_path)
    set_project(tmp_path)
    todo = tmp_path / "docs" / "clasi" / "todo"
    todo.mkdir(parents=True)
    return todo


def _advance_to_ticketing(work_dir, sprint_id: str) -> None:
    """Advance a sprint through review gates to ticketing phase for testing."""
    db_path = work_dir / "docs" / "clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # planning-docs -> architecture-review
    record_gate(db_path, sprint_id, "architecture_review", "passed")
    advance_phase(db_path, sprint_id)  # architecture-review -> stakeholder-review
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")
    advance_phase(db_path, sprint_id)  # stakeholder-review -> ticketing


class TestListTodos:
    def test_lists_todos(self, todo_dir):
        (todo_dir / "idea-one.md").write_text(
            "---\nstatus: pending\n---\n\n# Idea One\n\nSome details.\n"
        )
        (todo_dir / "idea-two.md").write_text(
            "---\nstatus: pending\n---\n\n# Idea Two\n\nMore details.\n"
        )

        result = json.loads(list_todos())
        assert len(result) == 2
        assert result[0]["filename"] == "idea-one.md"
        assert result[0]["title"] == "Idea One"
        assert result[0]["status"] == "pending"
        assert result[1]["filename"] == "idea-two.md"
        assert result[1]["title"] == "Idea Two"
        assert result[1]["status"] == "pending"

    def test_excludes_done_directory(self, todo_dir):
        (todo_dir / "active.md").write_text("# Active\n")
        done = todo_dir / "done"
        done.mkdir()
        (done / "finished.md").write_text("# Finished\n")

        result = json.loads(list_todos())
        assert len(result) == 1
        assert result[0]["filename"] == "active.md"

    def test_empty_directory(self, todo_dir):
        result = json.loads(list_todos())
        assert result == []

    def test_no_todo_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        result = json.loads(list_todos())
        assert result == []

    def test_file_without_heading(self, todo_dir):
        (todo_dir / "no-heading.md").write_text("Just some text.\n")

        result = json.loads(list_todos())
        assert len(result) == 1
        assert result[0]["title"] == "no-heading"

    def test_shows_sprint_ticket_linkage_for_in_progress(self, todo_dir):
        """In-progress TODOs show sprint and ticket linkage."""
        (todo_dir / "linked.md").write_text(
            "---\nstatus: in-progress\nsprint: '024'\n"
            "tickets:\n  - '024-001'\n  - '024-002'\n---\n\n# Linked\n"
        )
        (todo_dir / "pending.md").write_text(
            "---\nstatus: pending\n---\n\n# Pending\n"
        )

        result = json.loads(list_todos())
        linked = next(r for r in result if r["filename"] == "linked.md")
        pending = next(r for r in result if r["filename"] == "pending.md")

        assert linked["status"] == "in-progress"
        assert linked["sprint"] == "024"
        assert linked["tickets"] == ["024-001", "024-002"]

        assert pending["status"] == "pending"
        assert "sprint" not in pending
        assert "tickets" not in pending


class TestMoveTodoToDone:
    def test_moves_file(self, todo_dir):
        (todo_dir / "idea.md").write_text("# Idea\n")

        result = json.loads(move_todo_to_done("idea.md"))
        assert not (todo_dir / "idea.md").exists()
        assert (todo_dir / "done" / "idea.md").exists()
        assert result["new_path"].endswith("done/idea.md")

    def test_creates_done_directory(self, todo_dir):
        (todo_dir / "idea.md").write_text("# Idea\n")
        assert not (todo_dir / "done").exists()

        move_todo_to_done("idea.md")
        assert (todo_dir / "done").is_dir()

    def test_error_on_nonexistent(self, todo_dir):
        with pytest.raises(ValueError, match="TODO not found"):
            move_todo_to_done("nonexistent.md")

    def test_writes_traceability_frontmatter(self, todo_dir):
        (todo_dir / "idea.md").write_text("# Idea\n\nDetails.\n")

        move_todo_to_done("idea.md", sprint_id="005", ticket_ids=["001", "002"])

        content = (todo_dir / "done" / "idea.md").read_text()
        assert "status: done" in content
        assert 'sprint: "005"' in content or "sprint: '005'" in content
        assert "001" in content
        assert "002" in content

    def test_writes_status_done_without_sprint(self, todo_dir):
        (todo_dir / "idea.md").write_text("# Idea\n")

        move_todo_to_done("idea.md")

        content = (todo_dir / "done" / "idea.md").read_text()
        assert "status: done" in content

    def test_preserves_existing_frontmatter(self, todo_dir):
        (todo_dir / "idea.md").write_text(
            "---\nstatus: pending\n---\n\n# Idea\n"
        )

        move_todo_to_done("idea.md", sprint_id="005")

        content = (todo_dir / "done" / "idea.md").read_text()
        assert "status: done" in content
        assert 'sprint: "005"' in content or "sprint: '005'" in content


class TestCreateTicketWithTodo:
    """Tests for the create_ticket todo parameter (cross-referencing)."""

    @pytest.fixture
    def work_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        return tmp_path

    def _setup_sprint(self, work_dir):
        """Create a sprint and advance to ticketing phase."""
        create_sprint("Test Sprint")
        _advance_to_ticketing(work_dir, "001")
        # Create a TODO file
        todo = work_dir / "docs" / "clasi" / "todo"
        todo.mkdir(parents=True, exist_ok=True)
        return todo

    def test_creates_ticket_with_todo_field(self, work_dir):
        todo = self._setup_sprint(work_dir)
        (todo / "my-idea.md").write_text("---\nstatus: pending\n---\n\n# My Idea\n")

        result = json.loads(create_ticket("001", "Implement Idea", todo="my-idea.md"))
        from pathlib import Path
        ticket_fm = read_frontmatter(result["path"])
        assert ticket_fm["todo"] == "my-idea.md"

    def test_updates_todo_frontmatter_on_create(self, work_dir):
        todo = self._setup_sprint(work_dir)
        (todo / "my-idea.md").write_text("---\nstatus: pending\n---\n\n# My Idea\n")

        create_ticket("001", "Implement Idea", todo="my-idea.md")

        # TODO is now in in-progress/
        todo_fm = read_frontmatter(todo / "in-progress" / "my-idea.md")
        assert todo_fm["status"] == "in-progress"
        assert todo_fm["sprint"] == "001"
        assert "001-001" in todo_fm["tickets"]

    def test_multiple_todos(self, work_dir):
        todo = self._setup_sprint(work_dir)
        (todo / "idea-a.md").write_text("---\nstatus: pending\n---\n\n# Idea A\n")
        (todo / "idea-b.md").write_text("---\nstatus: pending\n---\n\n# Idea B\n")

        result = json.loads(
            create_ticket("001", "Both Ideas", todo=["idea-a.md", "idea-b.md"])
        )
        from pathlib import Path
        ticket_fm = read_frontmatter(result["path"])
        assert ticket_fm["todo"] == ["idea-a.md", "idea-b.md"]

        # Both TODOs should be in in-progress/
        fm_a = read_frontmatter(todo / "in-progress" / "idea-a.md")
        fm_b = read_frontmatter(todo / "in-progress" / "idea-b.md")
        assert fm_a["status"] == "in-progress"
        assert fm_b["status"] == "in-progress"
        assert fm_a["sprint"] == "001"
        assert fm_b["sprint"] == "001"

    def test_multiple_tickets_same_todo(self, work_dir):
        todo = self._setup_sprint(work_dir)
        (todo / "big-idea.md").write_text("---\nstatus: pending\n---\n\n# Big Idea\n")

        create_ticket("001", "Part 1", todo="big-idea.md")
        create_ticket("001", "Part 2", todo="big-idea.md")

        # TODO is in in-progress/
        todo_fm = read_frontmatter(todo / "in-progress" / "big-idea.md")
        assert todo_fm["tickets"] == ["001-001", "001-002"]

    def test_missing_todo_file_handled_gracefully(self, work_dir):
        self._setup_sprint(work_dir)
        # Don't create the TODO file -- should not raise
        result = json.loads(
            create_ticket("001", "Orphan", todo="nonexistent.md")
        )
        assert result["id"] == "001"

    def test_todo_moves_to_in_progress_not_done(self, work_dir):
        """TODO moves to in-progress/ (not done/) when ticket is created."""
        todo = self._setup_sprint(work_dir)
        (todo / "my-idea.md").write_text("---\nstatus: pending\n---\n\n# My Idea\n")

        create_ticket("001", "Implement Idea", todo="my-idea.md")

        # Should be in in-progress/, not in pending or done
        assert not (todo / "my-idea.md").exists()
        assert (todo / "in-progress" / "my-idea.md").exists()
        assert not (todo / "done" / "my-idea.md").exists()


class TestCloseSprintTodoHandling:
    """Tests for close_sprint TODO verification (no bulk-move)."""

    @pytest.fixture
    def work_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        return tmp_path

    def test_close_succeeds_when_todos_already_done(self, work_dir):
        """TODOs moved to done/ by ticket completion don't block close."""
        from clasi.tools.artifact_tools import move_ticket_to_done

        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / "docs" / "clasi" / "todo"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "my-idea.md").write_text("---\nstatus: pending\n---\n\n# My Idea\n")

        result = json.loads(create_ticket("001", "Task", todo="my-idea.md"))
        ticket_path = result["path"]

        # Complete ticket which triggers TODO completion
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)
        move_ticket_to_done(ticket_path)

        # TODO should already be in done/
        assert (todo / "done" / "my-idea.md").exists()

        result = json.loads(close_sprint("001"))
        # No bulk-move needed
        assert "moved_todos" not in result

    def test_close_reports_unresolved_in_progress_todos(self, work_dir):
        """In-progress TODOs are reported as unresolved, not bulk-moved."""
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / "docs" / "clasi" / "todo"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "idea.md").write_text("---\nstatus: pending\n---\n\n# Idea\n")

        create_ticket("001", "Task", todo="idea.md")
        # Don't complete the ticket — TODO stays in-progress
        result = json.loads(close_sprint("001"))
        assert "unresolved_todos" in result
        assert "idea.md" in result["unresolved_todos"]

    def test_close_without_linked_todos(self, work_dir):
        create_sprint("Sprint")
        result = json.loads(close_sprint("001"))
        assert "moved_todos" not in result
        assert "unresolved_todos" not in result

    def test_unlinked_todos_not_affected(self, work_dir):
        """TODOs not linked to the sprint are not touched."""
        from clasi.tools.artifact_tools import move_ticket_to_done

        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / "docs" / "clasi" / "todo"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "linked.md").write_text("---\nstatus: pending\n---\n\n# Linked\n")
        (todo / "unlinked.md").write_text(
            "---\nstatus: pending\n---\n\n# Unlinked\n"
        )

        result = json.loads(create_ticket("001", "Task", todo="linked.md"))
        ticket_path = result["path"]

        # Complete ticket to move linked TODO to done
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)
        move_ticket_to_done(ticket_path)

        close_sprint("001")

        # Linked should be in done/ (moved by ticket completion)
        assert (todo / "done" / "linked.md").exists()
        # Unlinked should still be in active dir
        assert (todo / "unlinked.md").exists()
        assert not (todo / "done" / "unlinked.md").exists()


class TestMoveTicketToDoneCompletesTodoGuard:
    """Tests for move_ticket_to_done respecting completes_todo_for."""

    @pytest.fixture
    def work_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        return tmp_path

    def _setup_sprint_with_todo(self, work_dir, todo_filename: str = "my-idea.md"):
        """Create sprint 001, create a ticket linked to todo_filename.

        Returns (todo_dir, ticket_path).
        """
        from clasi.tools.artifact_tools import move_ticket_to_done  # noqa: F401

        create_sprint("Test Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / "docs" / "clasi" / "todo"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / todo_filename).write_text(
            f"---\nstatus: pending\n---\n\n# My Idea\n"
        )

        result = json.loads(create_ticket("001", "Task", todo=todo_filename))
        ticket_path = result["path"]

        # Mark ticket as done in frontmatter
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)

        return todo, ticket_path

    def test_archives_single_sprint_todo_by_default(self, work_dir):
        """Existing behavior: no completes_todo field → TODO is archived."""
        from clasi.tools.artifact_tools import move_ticket_to_done

        todo, ticket_path = self._setup_sprint_with_todo(work_dir, "my-idea.md")

        result = json.loads(move_ticket_to_done(ticket_path))

        assert "completed_todos" in result
        assert "my-idea.md" in result["completed_todos"]
        assert (todo / "done" / "my-idea.md").exists()
        assert not (todo / "in-progress" / "my-idea.md").exists()

    def test_does_not_archive_when_completes_todo_scalar_false(self, work_dir):
        """completes_todo: false on the ticket → TODO is NOT archived."""
        from clasi.tools.artifact_tools import move_ticket_to_done

        todo, ticket_path = self._setup_sprint_with_todo(work_dir, "umbrella.md")

        # Add completes_todo: false to the ticket frontmatter
        fm = read_frontmatter(ticket_path)
        fm["completes_todo"] = False
        write_frontmatter(ticket_path, fm)

        result = json.loads(move_ticket_to_done(ticket_path))

        assert "completed_todos" not in result
        # TODO should still be in in-progress/
        assert (todo / "in-progress" / "umbrella.md").exists()
        assert not (todo / "done" / "umbrella.md").exists()

    def test_does_not_archive_when_any_ref_ticket_has_false(self, work_dir):
        """If any referencing ticket has completes_todo: false, TODO is NOT archived.

        Scenario: two tickets reference the same TODO; ticket 001 has
        completes_todo: false, ticket 002 has none (defaults to True).
        After both are done, moving ticket 002 to done must not archive the TODO.
        """
        from clasi.tools.artifact_tools import move_ticket_to_done

        create_sprint("Test Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / "docs" / "clasi" / "todo"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "umbrella.md").write_text("---\nstatus: pending\n---\n\n# Umbrella\n")

        # Create ticket 001 linked to umbrella.md
        r1 = json.loads(create_ticket("001", "Part One", todo="umbrella.md"))
        ticket1_path = r1["path"]

        # Create ticket 002 linked to umbrella.md
        r2 = json.loads(create_ticket("001", "Part Two", todo="umbrella.md"))
        ticket2_path = r2["path"]

        # Mark ticket 001 as done and give it completes_todo: false
        fm1 = read_frontmatter(ticket1_path)
        fm1["status"] = "done"
        fm1["completes_todo"] = False
        write_frontmatter(ticket1_path, fm1)
        move_ticket_to_done(ticket1_path)

        # Now mark ticket 002 as done (no completes_todo flag)
        fm2 = read_frontmatter(ticket2_path)
        fm2["status"] = "done"
        write_frontmatter(ticket2_path, fm2)
        result = json.loads(move_ticket_to_done(ticket2_path))

        # TODO must NOT be archived because ticket 001 suppressed it
        assert "completed_todos" not in result
        assert (todo / "in-progress" / "umbrella.md").exists()
        assert not (todo / "done" / "umbrella.md").exists()

    def test_completed_todos_not_populated_for_suppressed(self, work_dir):
        """result['completed_todos'] must not include suppressed TODOs."""
        from clasi.tools.artifact_tools import move_ticket_to_done

        todo, ticket_path = self._setup_sprint_with_todo(work_dir, "umbrella.md")

        fm = read_frontmatter(ticket_path)
        fm["completes_todo"] = False
        write_frontmatter(ticket_path, fm)

        result = json.loads(move_ticket_to_done(ticket_path))

        # Key must be absent entirely (not an empty list)
        assert "completed_todos" not in result
