"""Tests for claude_agent_skills.artifact_tools module."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from claude_agent_skills.artifact_tools import (
    close_sprint,
    create_sprint,
    create_ticket,
    get_sprint_status,
    insert_sprint,
    list_sprints,
    list_tickets,
    move_ticket_to_done,
    reopen_ticket,
    update_ticket_status,
)
from claude_agent_skills.frontmatter import read_frontmatter
from claude_agent_skills.state_db import (
    acquire_lock,
    advance_phase,
    get_sprint_state,
    record_gate,
)


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    """Set up a temporary working directory with docs/clasi/sprints/ structure."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _advance_to_ticketing(work_dir, sprint_id: str) -> None:
    """Advance a sprint through review gates to ticketing phase for testing."""
    db_path = work_dir / "docs" / "clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # planning-docs → architecture-review
    record_gate(db_path, sprint_id, "architecture_review", "passed")
    advance_phase(db_path, sprint_id)  # architecture-review → stakeholder-review
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")
    advance_phase(db_path, sprint_id)  # stakeholder-review → ticketing


class TestCreateSprint:
    def test_creates_directory_structure(self, work_dir):
        result = json.loads(create_sprint("Test Sprint"))
        sprint_dir = work_dir / "docs" / "clasi" / "sprints" / "001-test-sprint"
        assert sprint_dir.is_dir()
        assert (sprint_dir / "sprint.md").exists()
        assert not (sprint_dir / "brief.md").exists()
        assert (sprint_dir / "usecases.md").exists()
        assert (sprint_dir / "architecture-update.md").exists()
        assert (sprint_dir / "tickets").is_dir()
        assert (sprint_dir / "tickets" / "done").is_dir()
        assert result["id"] == "001"
        assert result["branch"] == "sprint/001-test-sprint"

    def test_auto_increments_id(self, work_dir):
        create_sprint("First")
        result = json.loads(create_sprint("Second"))
        assert result["id"] == "002"

    def test_same_title_gets_different_id(self, work_dir):
        r1 = json.loads(create_sprint("Test Sprint"))
        r2 = json.loads(create_sprint("Test Sprint"))
        assert r1["id"] == "001"
        assert r2["id"] == "002"

    def test_sprint_template_has_merged_sections(self, work_dir):
        create_sprint("My Sprint")
        sprint_dir = work_dir / "docs" / "clasi" / "sprints" / "001-my-sprint"
        content = (sprint_dir / "sprint.md").read_text()
        assert "## Problem" in content
        assert "## Solution" in content
        assert "## Success Criteria" in content
        assert "## Test Strategy" in content


class TestCreateSprintArchitectureUpdate:
    def test_creates_architecture_update_template(self, work_dir):
        """create_sprint generates a lightweight architecture-update template."""
        create_sprint("Test Sprint")
        sprint_dir = work_dir / "docs" / "clasi" / "sprints" / "001-test-sprint"
        arch = sprint_dir / "architecture-update.md"
        assert arch.exists()
        content = arch.read_text(encoding="utf-8")
        assert "## What Changed" in content
        assert "## Why" in content
        assert "## Impact on Existing Components" in content
        assert "## Migration Concerns" in content

    def test_does_not_copy_previous_architecture(self, work_dir):
        """create_sprint no longer copies the full architecture."""
        arch_dir = work_dir / "docs" / "clasi" / "architecture"
        arch_dir.mkdir(parents=True)
        (arch_dir / "architecture-015.md").write_text(
            "---\nstatus: approved\n---\n\n# Architecture\n\nExisting arch.\n",
            encoding="utf-8",
        )

        create_sprint("Test Sprint")
        sprint_dir = work_dir / "docs" / "clasi" / "sprints" / "001-test-sprint"
        # Should NOT have architecture.md (old behavior)
        assert not (sprint_dir / "architecture.md").exists()
        # Should have architecture-update.md (new behavior)
        assert (sprint_dir / "architecture-update.md").exists()

    def test_architecture_update_includes_sprint_id(self, work_dir):
        """architecture-update template includes the sprint ID."""
        create_sprint("Test Sprint")
        sprint_dir = work_dir / "docs" / "clasi" / "sprints" / "001-test-sprint"
        content = (sprint_dir / "architecture-update.md").read_text(encoding="utf-8")
        assert "001" in content


class TestCreateTicket:
    def test_creates_ticket(self, work_dir):
        create_sprint("My Sprint")
        _advance_to_ticketing(work_dir, "001")
        result = json.loads(create_ticket("001", "Add Feature"))
        assert result["id"] == "001"
        assert "001-add-feature.md" in result["path"]

    def test_auto_increments(self, work_dir):
        create_sprint("My Sprint")
        _advance_to_ticketing(work_dir, "001")
        create_ticket("001", "First")
        result = json.loads(create_ticket("001", "Second"))
        assert result["id"] == "002"

    def test_ticket_template_includes_testing_section(self, work_dir):
        create_sprint("My Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Test Feature"))
        from pathlib import Path
        content = Path(ticket["path"]).read_text(encoding="utf-8")
        assert "## Testing" in content
        assert "Existing tests to run" in content
        assert "New tests to write" in content
        assert "Verification command" in content
        assert "`uv run pytest`" in content

    def test_invalid_sprint(self, work_dir):
        with pytest.raises(ValueError, match="not found"):
            create_ticket("999", "Orphan")

    def test_blocked_before_ticketing_phase(self, work_dir):
        create_sprint("My Sprint")
        with pytest.raises(ValueError, match="planning-docs.*phase"):
            create_ticket("001", "Too Early")




class TestListSprints:
    def test_lists_sprints(self, work_dir):
        create_sprint("Sprint A")
        create_sprint("Sprint B")
        result = json.loads(list_sprints())
        assert len(result) == 2
        assert result[0]["id"] == "001"
        assert result[1]["id"] == "002"

    def test_filter_by_status(self, work_dir):
        create_sprint("Active Sprint")
        result = json.loads(list_sprints(status="planning"))
        assert len(result) == 1
        result = json.loads(list_sprints(status="done"))
        assert len(result) == 0

    def test_empty(self, work_dir):
        result = json.loads(list_sprints())
        assert result == []


class TestListTickets:
    def test_lists_tickets(self, work_dir):
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        create_ticket("001", "Task A")
        create_ticket("001", "Task B")
        result = json.loads(list_tickets())
        assert len(result) == 2

    def test_filter_by_sprint(self, work_dir):
        create_sprint("Sprint 1")
        create_sprint("Sprint 2")
        _advance_to_ticketing(work_dir, "001")
        _advance_to_ticketing(work_dir, "002")
        create_ticket("001", "Task in S1")
        create_ticket("002", "Task in S2")
        result = json.loads(list_tickets(sprint_id="001"))
        assert len(result) == 1
        assert result[0]["sprint_id"] == "001"

    def test_filter_by_status(self, work_dir):
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        create_ticket("001", "Todo Task")
        result = json.loads(list_tickets(status="todo"))
        assert len(result) == 1
        result = json.loads(list_tickets(status="done"))
        assert len(result) == 0


class TestGetSprintStatus:
    def test_status_with_tickets(self, work_dir):
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        create_ticket("001", "Task A")
        create_ticket("001", "Task B")
        result = json.loads(get_sprint_status("001"))
        assert result["id"] == "001"
        assert result["status"] == "planning"
        assert result["tickets"]["todo"] == 2
        assert result["tickets"]["done"] == 0

    def test_not_found(self, work_dir):
        with pytest.raises(ValueError, match="not found"):
            get_sprint_status("999")


class TestUpdateTicketStatus:
    def test_updates_status(self, work_dir):
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        result = json.loads(update_ticket_status(ticket["path"], "in-progress"))
        assert result["old_status"] == "todo"
        assert result["new_status"] == "in-progress"
        fm = read_frontmatter(ticket["path"])
        assert fm["status"] == "in-progress"

    def test_invalid_status(self, work_dir):
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        with pytest.raises(ValueError, match="Invalid status"):
            update_ticket_status(ticket["path"], "invalid")


class TestMoveTicketToDone:
    def test_moves_ticket(self, work_dir):
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        result = json.loads(move_ticket_to_done(ticket["path"]))
        assert not os.path.exists(result["old_path"])
        assert os.path.exists(result["new_path"])
        assert "done" in result["new_path"]

    def test_moves_plan_too(self, work_dir):
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        # Create a plan file
        from pathlib import Path
        plan_path = Path(ticket["path"]).parent / "001-task-plan.md"
        plan_path.write_text("# Plan\n", encoding="utf-8")
        result = json.loads(move_ticket_to_done(ticket["path"]))
        assert "plan_new_path" in result


class TestCloseSprint:
    def test_closes_sprint(self, work_dir):
        create_sprint("Sprint")
        result = json.loads(close_sprint("001"))
        assert "done" in result["new_path"]
        assert not os.path.exists(result["old_path"])
        # Verify status was updated
        from pathlib import Path
        sprint_file = Path(result["new_path"]) / "sprint.md"
        fm = read_frontmatter(sprint_file)
        assert fm["status"] == "done"


class TestInsertSprint:
    def test_inserts_and_renumbers(self, work_dir):
        create_sprint("Alpha")
        create_sprint("Beta")
        create_sprint("Gamma")

        result = json.loads(insert_sprint("001", "Urgent Fix"))

        # New sprint gets ID 002
        assert result["id"] == "002"
        assert "002-urgent-fix" in result["path"]
        assert result["phase"] == "planning-docs"

        # Old 002 (Beta) -> 003, old 003 (Gamma) -> 004
        assert len(result["renumbered"]) == 2
        assert result["renumbered"][0]["old_id"] == "002"
        assert result["renumbered"][0]["new_id"] == "003"
        assert result["renumbered"][1]["old_id"] == "003"
        assert result["renumbered"][1]["new_id"] == "004"

        # Verify directories exist with correct names
        sprints = work_dir / "docs" / "clasi" / "sprints"
        assert (sprints / "001-alpha").is_dir()
        assert (sprints / "002-urgent-fix").is_dir()
        assert (sprints / "003-beta").is_dir()
        assert (sprints / "004-gamma").is_dir()
        # Old directories should be gone
        assert not (sprints / "002-beta").exists()
        assert not (sprints / "003-gamma").exists()

    def test_renumbered_sprint_frontmatter_updated(self, work_dir):
        create_sprint("Alpha")
        create_sprint("Beta")
        insert_sprint("001", "Inserted")

        # Beta was 002, now should be 003
        sprints = work_dir / "docs" / "clasi" / "sprints"
        fm = read_frontmatter(sprints / "003-beta" / "sprint.md")
        assert fm["id"] == "003"
        assert fm["branch"] == "sprint/003-beta"

    def test_renumbered_sprint_body_updated(self, work_dir):
        create_sprint("Alpha")
        create_sprint("Beta")
        insert_sprint("001", "Inserted")

        sprints = work_dir / "docs" / "clasi" / "sprints"
        content = (sprints / "003-beta" / "sprint.md").read_text(encoding="utf-8")
        assert "Sprint 003" in content
        assert "Sprint 002" not in content

    def test_insert_at_end_no_renumbering(self, work_dir):
        create_sprint("Alpha")
        create_sprint("Beta")
        result = json.loads(insert_sprint("002", "Final"))

        assert result["id"] == "003"
        assert result["renumbered"] == []

        sprints = work_dir / "docs" / "clasi" / "sprints"
        assert (sprints / "003-final").is_dir()

    def test_refuses_renumbering_active_sprint(self, work_dir):
        create_sprint("Alpha")
        create_sprint("Beta")
        # Advance Beta (002) past planning-docs
        _advance_to_ticketing(work_dir, "002")

        with pytest.raises(ValueError, match="cannot be renumbered"):
            insert_sprint("001", "Urgent")

    def test_insert_with_tickets_updates_references(self, work_dir):
        create_sprint("Alpha")
        create_sprint("Beta")
        _advance_to_ticketing(work_dir, "002")

        # Create tickets in Beta (002)
        create_ticket("002", "Task A")
        create_ticket("002", "Task B")

        # Now insert after Alpha — but Beta is in ticketing phase, should fail
        with pytest.raises(ValueError, match="cannot be renumbered"):
            insert_sprint("001", "Inserted")

    def test_insert_after_nonexistent_sprint(self, work_dir):
        create_sprint("Alpha")
        with pytest.raises(ValueError, match="not found"):
            insert_sprint("999", "Ghost")

    def test_new_sprint_has_full_structure(self, work_dir):
        create_sprint("Alpha")
        result = json.loads(insert_sprint("001", "New Sprint"))

        from pathlib import Path
        sprint_dir = Path(result["path"])
        assert (sprint_dir / "sprint.md").exists()
        assert (sprint_dir / "usecases.md").exists()
        assert (sprint_dir / "architecture-update.md").exists()
        assert (sprint_dir / "tickets").is_dir()
        assert (sprint_dir / "tickets" / "done").is_dir()

    def test_insert_before_multiple_planning_sprints(self, work_dir):
        create_sprint("Alpha")
        create_sprint("Beta")
        create_sprint("Gamma")
        create_sprint("Delta")

        result = json.loads(insert_sprint("001", "Urgent"))
        assert result["id"] == "002"
        assert len(result["renumbered"]) == 3

        sprints = work_dir / "docs" / "clasi" / "sprints"
        assert (sprints / "001-alpha").is_dir()
        assert (sprints / "002-urgent").is_dir()
        assert (sprints / "003-beta").is_dir()
        assert (sprints / "004-gamma").is_dir()
        assert (sprints / "005-delta").is_dir()


class TestCreateOverview:
    def test_creates_overview(self, work_dir):
        from claude_agent_skills.artifact_tools import create_overview
        result = json.loads(create_overview())
        path = work_dir / "docs" / "clasi" / "overview.md"
        assert path.exists()
        content = path.read_text()
        assert "# Project Overview" in content
        assert "## Problem Statement" in content
        assert "## Sprint Roadmap" in content

    def test_rejects_duplicate(self, work_dir):
        from claude_agent_skills.artifact_tools import create_overview
        create_overview()
        with pytest.raises(ValueError, match="already exists"):
            create_overview()


def _advance_to_executing(work_dir, sprint_id: str) -> None:
    """Advance a sprint all the way to executing phase."""
    db_path = work_dir / "docs" / "clasi" / ".clasi.db"
    _advance_to_ticketing(work_dir, sprint_id)
    acquire_lock(str(db_path), sprint_id)
    advance_phase(str(db_path), sprint_id)  # ticketing → executing


class TestCloseSprintEdgeCases:
    def test_close_updates_status_and_moves(self, work_dir):
        create_sprint("Sprint")
        result = json.loads(close_sprint("001"))
        assert "done" in result["new_path"]
        assert not os.path.exists(result["old_path"])
        sprint_file = Path(result["new_path"]) / "sprint.md"
        fm = read_frontmatter(sprint_file)
        assert fm["status"] == "done"

    def test_close_advances_state_db(self, work_dir):
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        close_sprint("001")
        db_path = work_dir / "docs" / "clasi" / ".clasi.db"
        state = get_sprint_state(str(db_path), "001")
        assert state["phase"] == "done"

    def test_close_releases_lock(self, work_dir):
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        close_sprint("001")
        db_path = work_dir / "docs" / "clasi" / ".clasi.db"
        state = get_sprint_state(str(db_path), "001")
        assert state["lock"] is None

    @patch("claude_agent_skills.versioning.create_version_tag")
    @patch("claude_agent_skills.versioning.compute_next_version", return_value="0.20260214.1")
    def test_close_includes_version(self, mock_version, mock_tag, work_dir):
        # Create a pyproject.toml so versioning can find it
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        create_sprint("Sprint")
        result = json.loads(close_sprint("001"))
        assert result["version"] == "0.20260214.1"
        assert result["tag"] == "v0.20260214.1"
        mock_tag.assert_called_once_with("0.20260214.1")

    def test_close_without_version_file(self, work_dir):
        """close_sprint should still succeed when no version file exists."""
        create_sprint("Sprint")
        result = json.loads(close_sprint("001"))
        # Should not include version keys (or version is None)
        assert "done" in result["new_path"]

    def test_close_copies_architecture_update(self, work_dir):
        """close_sprint copies architecture-update.md to architecture dir."""
        create_sprint("Sprint")
        sprint_dir = work_dir / "docs" / "clasi" / "sprints" / "001-sprint"
        # Write content to the architecture-update file
        arch_update = sprint_dir / "architecture-update.md"
        arch_update.write_text(
            "---\nsprint: '001'\nstatus: draft\n---\n\n# Update\n\nSome changes.\n",
            encoding="utf-8",
        )
        close_sprint("001")
        arch_dir = work_dir / "docs" / "clasi" / "architecture"
        dest = arch_dir / "architecture-update-001.md"
        assert dest.exists()
        content = dest.read_text(encoding="utf-8")
        assert "Some changes." in content

    def test_close_without_architecture_update(self, work_dir):
        """close_sprint works even if no architecture-update.md exists."""
        create_sprint("Sprint")
        # Remove the architecture-update file
        sprint_dir = work_dir / "docs" / "clasi" / "sprints" / "001-sprint"
        arch_update = sprint_dir / "architecture-update.md"
        if arch_update.exists():
            arch_update.unlink()
        result = json.loads(close_sprint("001"))
        assert "done" in result["new_path"]

    def test_close_nonexistent_sprint(self, work_dir):
        with pytest.raises(ValueError, match="not found"):
            close_sprint("999")

    def test_close_destination_already_exists(self, work_dir):
        create_sprint("Sprint")
        done_dir = work_dir / "docs" / "clasi" / "sprints" / "done"
        done_dir.mkdir(parents=True)
        (done_dir / "001-sprint").mkdir()
        with pytest.raises(ValueError, match="already exists"):
            close_sprint("001")


class TestMoveTicketToDoneEdgeCases:
    def test_moves_ticket_preserves_frontmatter(self, work_dir):
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        result = json.loads(move_ticket_to_done(ticket["path"]))
        fm = read_frontmatter(result["new_path"])
        assert fm["status"] == "done"
        assert fm["title"] == "Task"

    def test_moves_plan_file_alongside_ticket(self, work_dir):
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        plan_path = Path(ticket["path"]).parent / "001-task-plan.md"
        plan_path.write_text("---\ntitle: Plan\n---\n\n# Plan\n", encoding="utf-8")
        result = json.loads(move_ticket_to_done(ticket["path"]))
        assert "plan_new_path" in result
        assert Path(result["plan_new_path"]).exists()
        assert not plan_path.exists()

    def test_no_plan_file_only_moves_ticket(self, work_dir):
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        result = json.loads(move_ticket_to_done(ticket["path"]))
        assert "plan_new_path" not in result
        assert Path(result["new_path"]).exists()

    def test_ticket_not_found(self, work_dir):
        with pytest.raises(ValueError, match="not found"):
            move_ticket_to_done("/nonexistent/ticket.md")

    def test_resolves_done_path_for_already_moved_ticket(self, work_dir):
        """If ticket is already in done/, resolve_artifact_path still finds it."""
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        result = json.loads(move_ticket_to_done(ticket["path"]))
        # Trying to move again using the original path should still find the file
        # in its new done/ location and attempt to move it
        result2 = json.loads(move_ticket_to_done(ticket["path"]))
        assert Path(result2["new_path"]).exists()


class TestReopenTicket:
    def test_reopens_from_done(self, work_dir):
        """Ticket in done/ is moved back to tickets/ with status reset."""
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        result = json.loads(reopen_ticket(ticket["path"]))
        assert result["old_status"] == "done"
        assert result["new_status"] == "todo"
        assert Path(result["old_path"]).parent.name == "done"
        assert Path(result["new_path"]).parent.name == "tickets"
        assert Path(result["new_path"]).exists()
        fm = read_frontmatter(result["new_path"])
        assert fm["status"] == "todo"

    def test_reopens_with_plan_file(self, work_dir):
        """Plan file in done/ is moved back alongside the ticket."""
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        plan_path = Path(ticket["path"]).parent / "001-task-plan.md"
        plan_path.write_text("---\ntitle: Plan\n---\n\n# Plan\n", encoding="utf-8")
        move_ticket_to_done(ticket["path"])

        result = json.loads(reopen_ticket(ticket["path"]))
        assert "plan_new_path" in result
        assert Path(result["plan_new_path"]).exists()
        assert "done" not in result["plan_new_path"]

    def test_reopens_already_active_ticket(self, work_dir):
        """Ticket not in done/ just gets status reset to todo."""
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "in-progress")

        result = json.loads(reopen_ticket(ticket["path"]))
        assert result["old_status"] == "in-progress"
        assert result["new_status"] == "todo"
        assert result["old_path"] == result["new_path"]
        fm = read_frontmatter(result["new_path"])
        assert fm["status"] == "todo"

    def test_ticket_not_found_raises_error(self, work_dir):
        """Nonexistent ticket raises ValueError."""
        with pytest.raises(ValueError, match="Ticket not found"):
            reopen_ticket("/nonexistent/ticket.md")

    def test_reopen_preserves_other_frontmatter(self, work_dir):
        """Reopening preserves fields like title, id, use-cases."""
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Important Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        result = json.loads(reopen_ticket(ticket["path"]))
        fm = read_frontmatter(result["new_path"])
        assert fm["status"] == "todo"
        assert fm["title"] == "Important Task"
        assert fm["id"] == "001"
