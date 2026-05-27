"""Tests for clasi.tools.artifact_tools module."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clasi.tools.artifact_tools import (
    close_sprint,
    create_sprint,
    create_ticket,
    detail_sprint,
    get_sprint_status,
    insert_sprint,
    list_sprints,
    list_tickets,
    move_ticket_to_done,
    reopen_ticket,
    update_ticket_status,
)
from clasi.frontmatter import read_frontmatter, write_frontmatter
from clasi.mcp_server import set_project
from clasi.state_db import (
    acquire_lock,
    advance_phase,
    get_recovery_state,
    get_sprint_state,
    record_gate,
    write_recovery_state,
)


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    """Set up a temporary working directory with .clasi/sprints/ structure."""
    monkeypatch.chdir(tmp_path)
    set_project(tmp_path)
    return tmp_path


def _advance_to_ticketing(work_dir, sprint_id: str) -> None:
    """Advance a sprint through review gates to ticketing phase for testing."""
    db_path = work_dir / ".clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # roadmap → planning-docs
    advance_phase(db_path, sprint_id)  # planning-docs → architecture-review
    record_gate(db_path, sprint_id, "architecture_review", "passed")
    advance_phase(db_path, sprint_id)  # architecture-review → stakeholder-review
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")
    advance_phase(db_path, sprint_id)  # stakeholder-review → ticketing


class TestCreateSprint:
    def test_creates_directory_structure(self, work_dir):
        """create_sprint (roadmap phase) writes only sprint.md — no other artifacts."""
        result = json.loads(create_sprint("Test Sprint"))
        sprint_dir = work_dir / ".clasi" / "sprints" / "001-test-sprint"
        assert sprint_dir.is_dir()
        assert (sprint_dir / "sprint.md").exists()
        assert not (sprint_dir / "brief.md").exists()
        # Lightweight roadmap-phase sprint: only sprint.md is written
        assert not (sprint_dir / "usecases.md").exists()
        assert not (sprint_dir / "architecture-update.md").exists()
        assert not (sprint_dir / "tickets").exists()
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
        sprint_dir = work_dir / ".clasi" / "sprints" / "001-my-sprint"
        content = (sprint_dir / "sprint.md").read_text()
        assert "## Problem" in content
        assert "## Solution" in content
        assert "## Success Criteria" in content
        assert "## Test Strategy" in content


class TestDetailSprint:
    """Tests for the detail_sprint MCP tool."""

    def test_success_path_roadmap_to_planning_docs(self, work_dir):
        """detail_sprint on a roadmap sprint scaffolds files and returns correct JSON."""
        create_sprint("My Sprint")
        result = json.loads(detail_sprint("001"))
        assert result["sprint_id"] == "001"
        assert result["phase"] == "planning-docs"
        assert len(result["files_written"]) >= 2
        # usecases.md and architecture-update.md should be among files written
        written_names = [Path(f).name for f in result["files_written"]]
        assert "usecases.md" in written_names
        assert "architecture-update.md" in written_names

    def test_scaffolds_full_directory_structure(self, work_dir):
        """After detail_sprint, tickets/ and tickets/done/ directories exist."""
        create_sprint("My Sprint")
        detail_sprint("001")
        sprint_dir = work_dir / ".clasi" / "sprints" / "001-my-sprint"
        assert (sprint_dir / "usecases.md").exists()
        assert (sprint_dir / "architecture-update.md").exists()
        assert (sprint_dir / "tickets").is_dir()
        assert (sprint_dir / "tickets" / "done").is_dir()

    def test_phase_advances_to_planning_docs(self, work_dir):
        """get_sprint_phase returns planning-docs after detail_sprint."""
        from clasi.tools.artifact_tools import get_sprint_phase
        create_sprint("My Sprint")
        detail_sprint("001")
        phase_result = json.loads(get_sprint_phase("001"))
        assert phase_result["phase"] == "planning-docs"

    def test_error_if_sprint_not_in_roadmap(self, work_dir):
        """detail_sprint returns JSON error if sprint is not in roadmap phase."""
        create_sprint("My Sprint")
        db_path = work_dir / ".clasi" / ".clasi.db"
        # Advance past roadmap manually
        advance_phase(db_path, "001")  # roadmap -> planning-docs
        result = json.loads(detail_sprint("001"))
        assert "error" in result
        assert "roadmap" in result["error"]

    def test_error_if_already_detail_planned(self, work_dir):
        """detail_sprint returns JSON error if called a second time."""
        create_sprint("My Sprint")
        detail_sprint("001")
        # Second call should fail
        result = json.loads(detail_sprint("001"))
        assert "error" in result

    def test_error_if_sprint_not_found(self, work_dir):
        """detail_sprint returns JSON error for a nonexistent sprint ID."""
        result = json.loads(detail_sprint("999"))
        assert "error" in result


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
        with pytest.raises(ValueError, match="roadmap.*phase"):
            create_ticket("001", "Too Early")

    def test_auto_links_sprint_issues_when_no_issue_param(self, work_dir):
        """create_ticket without issue param auto-links from sprint.md todos."""
        create_sprint("My Sprint")
        _advance_to_ticketing(work_dir, "001")
        # Add todos field to sprint.md frontmatter
        sprint_md = (
            work_dir / ".clasi" / "sprints" / "001-my-sprint" / "sprint.md"
        )
        fm = read_frontmatter(sprint_md)
        fm["todos"] = ["idea-a.md", "idea-b.md"]
        write_frontmatter(sprint_md, fm)

        result = json.loads(create_ticket("001", "Auto Linked"))
        ticket_fm = read_frontmatter(result["path"])
        assert ticket_fm["issue"] == ["idea-a.md", "idea-b.md"]

    def test_explicit_issue_not_overridden_by_sprint_todos(self, work_dir):
        """Explicit issue param takes priority over sprint.md todos."""
        create_sprint("My Sprint")
        _advance_to_ticketing(work_dir, "001")
        sprint_md = (
            work_dir / ".clasi" / "sprints" / "001-my-sprint" / "sprint.md"
        )
        fm = read_frontmatter(sprint_md)
        fm["todos"] = ["idea-a.md", "idea-b.md"]
        write_frontmatter(sprint_md, fm)

        result = json.loads(create_ticket("001", "Explicit", issue="explicit.md"))
        ticket_fm = read_frontmatter(result["path"])
        assert ticket_fm["issue"] == "explicit.md"

    def test_no_todos_field_no_auto_link(self, work_dir):
        """When sprint.md has no todos field, no auto-linking happens."""
        create_sprint("My Sprint")
        _advance_to_ticketing(work_dir, "001")
        result = json.loads(create_ticket("001", "No Link"))
        ticket_fm = read_frontmatter(result["path"])
        # issue field should be absent or empty (no auto-link occurred)
        assert not ticket_fm.get("issue")


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
        result = json.loads(list_sprints(status="roadmap"))
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
        create_ticket("001", "Open Task")
        result = json.loads(list_tickets(status="open"))
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
        assert result["status"] == "roadmap"
        assert result["tickets"]["open"] == 2
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
        assert result["old_status"] == "open"
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
        assert result["phase"] == "roadmap"

        # Old 002 (Beta) -> 003, old 003 (Gamma) -> 004
        assert len(result["renumbered"]) == 2
        assert result["renumbered"][0]["old_id"] == "002"
        assert result["renumbered"][0]["new_id"] == "003"
        assert result["renumbered"][1]["old_id"] == "003"
        assert result["renumbered"][1]["new_id"] == "004"

        # Verify directories exist with correct names
        sprints = work_dir / ".clasi" / "sprints"
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
        sprints = work_dir / ".clasi" / "sprints"
        fm = read_frontmatter(sprints / "003-beta" / "sprint.md")
        assert fm["id"] == "003"
        assert fm["branch"] == "sprint/003-beta"

    def test_renumbered_sprint_body_updated(self, work_dir):
        create_sprint("Alpha")
        create_sprint("Beta")
        insert_sprint("001", "Inserted")

        sprints = work_dir / ".clasi" / "sprints"
        content = (sprints / "003-beta" / "sprint.md").read_text(encoding="utf-8")
        assert "Sprint 003" in content
        assert "Sprint 002" not in content

    def test_insert_at_end_no_renumbering(self, work_dir):
        create_sprint("Alpha")
        create_sprint("Beta")
        result = json.loads(insert_sprint("002", "Final"))

        assert result["id"] == "003"
        assert result["renumbered"] == []

        sprints = work_dir / ".clasi" / "sprints"
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

        sprints = work_dir / ".clasi" / "sprints"
        assert (sprints / "001-alpha").is_dir()
        assert (sprints / "002-urgent").is_dir()
        assert (sprints / "003-beta").is_dir()
        assert (sprints / "004-gamma").is_dir()
        assert (sprints / "005-delta").is_dir()


def _advance_to_executing(work_dir, sprint_id: str) -> None:
    """Advance a sprint all the way to executing phase."""
    db_path = work_dir / ".clasi" / ".clasi.db"
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
        db_path = work_dir / ".clasi" / ".clasi.db"
        state = get_sprint_state(str(db_path), "001")
        assert state["phase"] == "done"

    def test_close_releases_lock(self, work_dir):
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        close_sprint("001")
        db_path = work_dir / ".clasi" / ".clasi.db"
        state = get_sprint_state(str(db_path), "001")
        assert state["lock"] is None

    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260214.1")
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
        sprint_dir = work_dir / ".clasi" / "sprints" / "001-sprint"
        # Write content to the architecture-update file
        arch_update = sprint_dir / "architecture-update.md"
        arch_update.write_text(
            "---\nsprint: '001'\nstatus: draft\n---\n\n# Update\n\nSome changes.\n",
            encoding="utf-8",
        )
        close_sprint("001")
        arch_dir = work_dir / ".clasi" / "architecture"
        dest = arch_dir / "architecture-update-001.md"
        assert dest.exists()
        content = dest.read_text(encoding="utf-8")
        assert "Some changes." in content

    def test_close_without_architecture_update(self, work_dir):
        """close_sprint works even if no architecture-update.md exists."""
        create_sprint("Sprint")
        # Remove the architecture-update file
        sprint_dir = work_dir / ".clasi" / "sprints" / "001-sprint"
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
        done_dir = work_dir / ".clasi" / "sprints" / "done"
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
        assert result["new_status"] == "open"
        assert Path(result["old_path"]).parent.name == "done"
        assert Path(result["new_path"]).parent.name == "tickets"
        assert Path(result["new_path"]).exists()
        fm = read_frontmatter(result["new_path"])
        assert fm["status"] == "open"

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
        """Ticket not in done/ just gets status reset to open."""
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "in-progress")

        result = json.loads(reopen_ticket(ticket["path"]))
        assert result["old_status"] == "in-progress"
        assert result["new_status"] == "open"
        assert result["old_path"] == result["new_path"]
        fm = read_frontmatter(result["new_path"])
        assert fm["status"] == "open"

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
        assert fm["status"] == "open"
        assert fm["title"] == "Important Task"
        assert fm["id"] == "001"


class TestCloseSprintFull:
    """Tests for close_sprint with branch_name (full lifecycle)."""

    def _make_subprocess_result(self, returncode=0, stdout="", stderr=""):
        result = MagicMock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = stderr
        return result

    def test_branch_name_none_falls_back_to_legacy(self, work_dir):
        """Omitting branch_name uses legacy behavior."""
        create_sprint("Sprint")
        result = json.loads(close_sprint("001"))
        # Legacy result has old_path/new_path but no "status" key
        assert "done" in result["new_path"]
        assert "status" not in result  # Legacy format

    def test_branch_name_none_explicit_falls_back(self, work_dir):
        """Explicitly passing branch_name=None uses legacy behavior."""
        create_sprint("Sprint")
        result = json.loads(close_sprint("001", branch_name=None))
        assert "done" in result["new_path"]
        assert "status" not in result

    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    def test_full_lifecycle_success(self, mock_run, mock_ver, mock_tag, work_dir):
        """Full lifecycle returns structured success JSON."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        # Create a ticket and move to done
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        # Mock subprocess calls: pytest, git add -A (version bump), git commit (version bump),
        # git status --porcelain (.clasi.db guard, clean→no-op), git rev-parse --verify branch
        # (merge check), git merge-base --is-ancestor, git rebase, git checkout master,
        # git merge --no-ff, git push --tags, git rev-parse --verify branch (delete check),
        # git branch -d
        mock_run.side_effect = [
            self._make_subprocess_result(0, "all tests passed"),  # pytest
            self._make_subprocess_result(0),  # git add -A (version bump)
            self._make_subprocess_result(0),  # git commit (version bump)
            self._make_subprocess_result(0, ""),  # git status --porcelain .clasi.db (clean)
            self._make_subprocess_result(0),  # git rev-parse --verify branch (merge check)
            self._make_subprocess_result(1),  # git merge-base --is-ancestor (not yet merged)
            self._make_subprocess_result(0),  # git rebase master sprint/001-sprint
            self._make_subprocess_result(0),  # git checkout master
            self._make_subprocess_result(0),  # git merge --no-ff
            self._make_subprocess_result(0),  # git push --tags
            self._make_subprocess_result(0),  # git rev-parse --verify branch (delete check)
            self._make_subprocess_result(0),  # git branch -d
        ]

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "success"
        assert "done" in result["new_path"]
        assert result["git"]["merged"] is True
        assert result["git"]["merge_target"] == "master"
        assert result["git"]["branch_name"] == "sprint/001-sprint"

    @patch("subprocess.run")
    def test_test_failure_returns_error(self, mock_run, work_dir):
        """When tests fail, return structured error with recovery."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        mock_run.return_value = self._make_subprocess_result(
            1, "FAILED test_foo.py", "1 failed"
        )

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "error"
        assert result["error"]["step"] == "tests"
        assert "precondition_verification" in result["completed_steps"]
        assert "tests" not in result["completed_steps"]
        assert result["error"]["recovery"]["instruction"] is not None

    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    def test_merge_conflict_returns_error(self, mock_run, mock_ver, mock_tag, work_dir):
        """When merge has conflicts, return structured error."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        mock_run.side_effect = [
            self._make_subprocess_result(0, "all tests passed"),  # pytest
            self._make_subprocess_result(0),  # git add -A (version bump)
            self._make_subprocess_result(0),  # git commit (version bump)
            self._make_subprocess_result(0, ""),  # git status --porcelain .clasi.db (clean)
            self._make_subprocess_result(0),  # git rev-parse --verify
            self._make_subprocess_result(1),  # git merge-base (not ancestor)
            self._make_subprocess_result(0),  # git rebase master sprint/001-sprint
            self._make_subprocess_result(0),  # git checkout master
            self._make_subprocess_result(1, "", "CONFLICT in foo.py"),  # git merge --no-ff
            self._make_subprocess_result(0, "foo.py\n"),  # git diff --name-only
            self._make_subprocess_result(0),  # git merge --abort
        ]

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "error"
        assert result["error"]["step"] == "merge"
        assert "foo.py" in result["error"]["recovery"]["allowed_paths"]
        assert "archive" in result["completed_steps"]

        # Verify recovery state was written
        db_path = work_dir / ".clasi" / ".clasi.db"
        recovery = get_recovery_state(db_path)
        assert recovery is not None
        assert recovery["step"] == "merge"

    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    def test_already_merged_branch_is_idempotent(self, mock_run, mock_ver, mock_tag, work_dir):
        """If branch doesn't exist, merge step is skipped."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        mock_run.side_effect = [
            self._make_subprocess_result(0, "all passed"),  # pytest
            self._make_subprocess_result(0),  # git add -A (version bump)
            self._make_subprocess_result(0),  # git commit (version bump)
            self._make_subprocess_result(0, ""),  # git status --porcelain .clasi.db (clean)
            self._make_subprocess_result(1),  # git rev-parse --verify (branch gone, merge check)
            self._make_subprocess_result(0),  # git push --tags
            self._make_subprocess_result(1),  # git rev-parse --verify (branch gone, delete check)
        ]

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "success"
        assert result["git"]["merged"] is True
        assert result["git"]["branch_deleted"] is False  # branch didn't exist

    def test_precondition_ticket_not_done_returns_error(self, work_dir):
        """Ticket not in done status causes precondition error."""
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "in-progress")

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "error"
        assert result["error"]["step"] == "precondition"
        assert "in-progress" in result["error"]["message"]

    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    def test_self_repair_moves_done_ticket(self, mock_run, mock_ver, mock_tag, work_dir):
        """Ticket with done status but in tickets/ (not done/) gets moved."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        ticket = json.loads(create_ticket("001", "Task"))
        # Set status to done but don't move to done/
        update_ticket_status(ticket["path"], "done")

        mock_run.side_effect = [
            self._make_subprocess_result(0, "all passed"),  # pytest
            self._make_subprocess_result(0),  # git add -A (version bump)
            self._make_subprocess_result(0),  # git commit (version bump)
            self._make_subprocess_result(0, ""),  # git status --porcelain .clasi.db (clean)
            self._make_subprocess_result(1),  # git rev-parse --verify (merge: branch gone)
            self._make_subprocess_result(0),  # git push --tags
            self._make_subprocess_result(1),  # git rev-parse --verify (delete: branch gone)
        ]

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "success"
        assert any("moved ticket" in r for r in result["repairs"])

    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    def test_structured_result_format(self, mock_run, mock_ver, mock_tag, work_dir):
        """Verify all expected fields in success result."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        mock_run.side_effect = [
            self._make_subprocess_result(0),  # pytest
            self._make_subprocess_result(0),  # git add -A (version bump)
            self._make_subprocess_result(0),  # git commit (version bump)
            self._make_subprocess_result(0, ""),  # git status --porcelain .clasi.db (clean)
            self._make_subprocess_result(1),  # git rev-parse --verify (merge: branch gone)
            self._make_subprocess_result(0),  # git push --tags
            self._make_subprocess_result(1),  # git rev-parse --verify (delete: branch gone)
        ]

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "success"
        assert "old_path" in result
        assert "new_path" in result
        assert "repairs" in result
        assert isinstance(result["repairs"], list)
        assert "git" in result
        assert "merged" in result["git"]
        assert "merge_target" in result["git"]
        assert "tags_pushed" in result["git"]
        assert "branch_deleted" in result["git"]
        assert "branch_name" in result["git"]

    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    def test_recovery_state_cleared_on_success(self, mock_run, mock_ver, mock_tag, work_dir):
        """Recovery state is cleared after successful close."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        # Pre-write a recovery state
        db_path = work_dir / ".clasi" / ".clasi.db"
        write_recovery_state(str(db_path), "001", "tests", [], "old failure")

        mock_run.side_effect = [
            self._make_subprocess_result(0),  # pytest
            self._make_subprocess_result(0),  # git add -A (version bump)
            self._make_subprocess_result(0),  # git commit (version bump)
            self._make_subprocess_result(0, ""),  # git status --porcelain .clasi.db (clean)
            self._make_subprocess_result(1),  # git rev-parse --verify (merge: branch gone)
            self._make_subprocess_result(0),  # git push --tags
            self._make_subprocess_result(1),  # git rev-parse --verify (delete: branch gone)
        ]

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "success"

        # Recovery state should be cleared
        recovery = get_recovery_state(db_path)
        assert recovery is None


class TestSystemRoundtrip:
    """System-level end-to-end tests covering create_sprint → list_sprints → detail_sprint flow."""

    def test_detail_sprint_tool_roundtrip(self, work_dir):
        """Full roundtrip: create_sprint → detail_sprint → get_sprint_phase → assert artifacts exist."""
        from clasi.tools.artifact_tools import get_sprint_phase

        # Create a roadmap sprint
        create_result = json.loads(create_sprint("Roundtrip Sprint"))
        sprint_id = create_result["id"]
        assert create_result["phase"] == "roadmap"

        # Advance it via detail_sprint
        detail_result = json.loads(detail_sprint(sprint_id))
        assert "error" not in detail_result
        assert detail_result["sprint_id"] == sprint_id
        assert detail_result["phase"] == "planning-docs"

        # Verify phase via get_sprint_phase
        phase_result = json.loads(get_sprint_phase(sprint_id))
        assert phase_result["phase"] == "planning-docs"

        # Verify all three artifact files exist
        sprint_dir = work_dir / ".clasi" / "sprints" / f"{sprint_id}-roundtrip-sprint"
        assert (sprint_dir / "sprint.md").exists()
        assert (sprint_dir / "usecases.md").exists()
        assert (sprint_dir / "architecture-update.md").exists()

    def test_detail_sprint_rejects_non_roadmap(self, work_dir):
        """detail_sprint on a sprint already in planning-docs returns error with non-empty message."""
        create_sprint("Already Detailed")
        # Advance to planning-docs first
        detail_sprint("001")
        # Calling detail_sprint again on planning-docs sprint must return an error
        result = json.loads(detail_sprint("001"))
        assert "error" in result
        assert len(result["error"]) > 0

    def test_list_sprints_status_roadmap(self, work_dir):
        """list_sprints(status='roadmap') returns only the sprint not yet detailed."""
        create_sprint("Sprint Alpha")   # 001 — stays roadmap
        create_sprint("Sprint Beta")    # 002 — will be advanced to planning-docs

        # Advance sprint 002 via detail_sprint
        detail_result = json.loads(detail_sprint("002"))
        assert detail_result["phase"] == "planning-docs"

        # Only sprint 001 should appear in roadmap filter
        roadmap_sprints = json.loads(list_sprints(status="roadmap"))
        roadmap_ids = [s["id"] for s in roadmap_sprints]
        assert "001" in roadmap_ids
        assert "002" not in roadmap_ids

    def test_list_sprints_default_returns_all(self, work_dir):
        """list_sprints() with no filter returns both roadmap and planning-docs sprints."""
        create_sprint("Sprint Alpha")   # 001 — stays roadmap
        create_sprint("Sprint Beta")    # 002 — will be advanced to planning-docs

        # Advance sprint 002 via detail_sprint
        detail_sprint("002")

        # No-filter call must return both sprints
        all_sprints = json.loads(list_sprints())
        all_ids = [s["id"] for s in all_sprints]
        assert "001" in all_ids
        assert "002" in all_ids
        assert len(all_sprints) == 2


class TestCloseSprintLockAndDbGuard:
    """Tests for .clasi.db commit guard (step 5b) and lock release on merge failure."""

    def _make_subprocess_result(self, returncode=0, stdout="", stderr=""):
        result = MagicMock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = stderr
        return result

    @patch("subprocess.run")
    def test_dirty_db_guard_commits_when_versioning_disabled(self, mock_run, work_dir):
        """Guard stages and commits .clasi.db when dirty and versioning is manual."""
        # Disable versioning so no version bump subprocess calls happen
        settings_dir = work_dir / ".clasi"
        settings_dir.mkdir(parents=True, exist_ok=True)
        (settings_dir / "settings.yaml").write_text("version_trigger: manual\n")

        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        # Call sequence (no version bump with manual trigger):
        # pytest, git status --porcelain (dirty), git rev-parse --abbrev-ref HEAD
        # (on sprint branch), git add .clasi.db, git commit,
        # git rev-parse --verify (branch gone), git push --tags (skipped),
        # git rev-parse --verify (delete, branch gone)
        mock_run.side_effect = [
            self._make_subprocess_result(0, ""),        # pytest (pass)
            self._make_subprocess_result(0, " M .clasi/.clasi.db\n"),  # git status --porcelain (dirty)
            self._make_subprocess_result(0, "sprint/001-sprint\n"),  # git rev-parse --abbrev-ref HEAD
            self._make_subprocess_result(0),            # git add .clasi.db
            self._make_subprocess_result(0),            # git commit
            self._make_subprocess_result(1),            # git rev-parse --verify (branch gone)
            self._make_subprocess_result(1),            # git rev-parse --verify (delete, branch gone)
        ]

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "success"

        # Verify that git add and git commit were called with the .clasi.db path
        calls = mock_run.call_args_list
        db_path_str = str(work_dir / ".clasi" / ".clasi.db")
        add_calls = [c for c in calls if c.args[0][:2] == ["git", "add"] and db_path_str in c.args[0]]
        commit_calls = [c for c in calls if c.args[0][:3] == ["git", "commit", "-m"] and "chore: update .clasi.db" in c.args[0]]
        assert len(add_calls) == 1, "Expected one git add .clasi.db call"
        assert len(commit_calls) == 1, "Expected one git commit chore: update .clasi.db call"

    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    def test_dirty_db_guard_is_noop_when_versioning_cleans_it(
        self, mock_run, mock_ver, mock_tag, work_dir
    ):
        """Guard is a no-op when git status shows .clasi.db is clean (version bump committed it)."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        # Call sequence (with version bump):
        # pytest, git add -A (version bump), git commit (version bump),
        # git status --porcelain (empty = clean, guard is no-op),
        # git rev-parse --verify (branch gone), git push --tags, git rev-parse --verify (delete)
        mock_run.side_effect = [
            self._make_subprocess_result(0),        # pytest
            self._make_subprocess_result(0),        # git add -A (version bump)
            self._make_subprocess_result(0),        # git commit (version bump)
            self._make_subprocess_result(0, ""),    # git status --porcelain (clean)
            self._make_subprocess_result(1),        # git rev-parse --verify (branch gone)
            self._make_subprocess_result(0),        # git push --tags
            self._make_subprocess_result(1),        # git rev-parse --verify (delete, gone)
        ]

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "success"

        # Verify no git add .clasi.db or "chore: update .clasi.db" commit was made
        calls = mock_run.call_args_list
        db_path_str = str(work_dir / ".clasi" / ".clasi.db")
        db_add_calls = [c for c in calls if c.args[0][:2] == ["git", "add"] and db_path_str in c.args[0]]
        db_commit_calls = [c for c in calls if c.args[0][:3] == ["git", "commit", "-m"] and "chore: update .clasi.db" in c.args[0]]
        assert len(db_add_calls) == 0, "Guard should not run git add .clasi.db when tree is clean"
        assert len(db_commit_calls) == 0, "Guard should not commit .clasi.db when tree is clean"

    @patch("subprocess.run")
    def test_lock_released_after_merge_failure(self, mock_run, work_dir):
        """Execution lock is released in finally block even when merge raises RuntimeError."""
        # Disable versioning for a simpler call sequence
        settings_dir = work_dir / ".clasi"
        settings_dir.mkdir(parents=True, exist_ok=True)
        (settings_dir / "settings.yaml").write_text("version_trigger: manual\n")

        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        db_path = work_dir / ".clasi" / ".clasi.db"

        # Verify lock is held before close_sprint (lock is a dict when held, None when not)
        state_before = get_sprint_state(str(db_path), "001")
        assert state_before["lock"] is not None

        # Call sequence (no version bump):
        # pytest, git status --porcelain (clean), git rev-parse --verify (branch exists),
        # git merge-base (not ancestor), git rebase (fails with non-zero) -> abort,
        # (merge raises RuntimeError, finally block runs release_lock)
        mock_run.side_effect = [
            self._make_subprocess_result(0, ""),    # pytest (pass)
            self._make_subprocess_result(0, ""),    # git status --porcelain (clean)
            self._make_subprocess_result(0),        # git rev-parse --verify (branch exists)
            self._make_subprocess_result(1),        # git merge-base (not ancestor)
            self._make_subprocess_result(1, "", "conflict during rebase"),  # git rebase (fails)
            self._make_subprocess_result(0),        # git rebase --abort
        ]

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "error"
        assert result["error"]["step"] == "merge"

        # The execution lock MUST be released even though merge failed
        state_after = get_sprint_state(str(db_path), "001")
        assert state_after["lock"] is None, "Lock must be released after merge failure"

    @patch("subprocess.run")
    def test_db_guard_skipped_when_not_on_sprint_branch(self, mock_run, work_dir):
        """Guard does not commit .clasi.db when HEAD is not the sprint branch."""
        # Disable versioning for a simpler call sequence
        settings_dir = work_dir / ".clasi"
        settings_dir.mkdir(parents=True, exist_ok=True)
        (settings_dir / "settings.yaml").write_text("version_trigger: manual\n")

        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        # db is dirty but HEAD is not the sprint branch (e.g. accidentally on master)
        mock_run.side_effect = [
            self._make_subprocess_result(0, ""),        # pytest (pass)
            self._make_subprocess_result(0, " M .clasi/.clasi.db\n"),  # git status --porcelain (dirty)
            self._make_subprocess_result(0, "master\n"),  # git rev-parse --abbrev-ref HEAD (wrong branch)
            # Guard skipped — no git add or git commit for .clasi.db
            self._make_subprocess_result(1),            # git rev-parse --verify (branch gone)
            self._make_subprocess_result(1),            # git rev-parse --verify (delete, branch gone)
        ]

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        # close_sprint still succeeds (guard just doesn't commit)
        assert result["status"] == "success"

        # Verify no targeted .clasi.db commit was made
        calls = mock_run.call_args_list
        db_path_str = str(work_dir / ".clasi" / ".clasi.db")
        db_commit_calls = [c for c in calls if c.args[0][:3] == ["git", "commit", "-m"] and "chore: update .clasi.db" in c.args[0]]
        assert len(db_commit_calls) == 0, "Guard must not commit when not on sprint branch"


class TestCloseSprintPreconditionSubcases:
    """Tests for _close_sprint_full precondition sub-case discrimination (ticket 008-002)."""

    def test_close_sprint_malformed_frontmatter_error(self, work_dir):
        """Malformed sprint.md frontmatter returns specific error naming the file."""
        create_sprint("Sprint")
        sprint_dir = work_dir / ".clasi" / "sprints" / "001-sprint"
        sprint_md = sprint_dir / "sprint.md"
        # Corrupt the opening fence so frontmatter is unparseable
        sprint_md.write_text("--- BROKEN FENCE\nid: '001'\n---\n\n# Sprint\n", encoding="utf-8")

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))

        assert result["status"] == "error"
        assert result["error"]["step"] == "precondition"
        # Message must name the file path
        assert str(sprint_md) in result["error"]["message"]
        # Instruction must say to fix the frontmatter, not to create/restore directory
        instruction = result["error"]["recovery"]["instruction"]
        assert "frontmatter" in instruction.lower()
        assert "create or restore" not in instruction.lower()

    def test_close_sprint_id_mismatch_error(self, work_dir):
        """Sprint.md with mismatched id field returns specific error naming file and ids."""
        create_sprint("Sprint")
        sprint_dir = work_dir / ".clasi" / "sprints" / "001-sprint"
        sprint_md = sprint_dir / "sprint.md"
        # Valid frontmatter fence but wrong id
        sprint_md.write_text(
            "---\nid: '999'\ntitle: Sprint\nstatus: roadmap\n---\n\n# Sprint\n",
            encoding="utf-8",
        )

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))

        assert result["status"] == "error"
        assert result["error"]["step"] == "precondition"
        # Message must name the found id and the requested id
        assert "999" in result["error"]["message"]
        assert "001" in result["error"]["message"]
        # Instruction must say to correct the id field, not to create/restore directory
        instruction = result["error"]["recovery"]["instruction"]
        assert "id" in instruction.lower()
        assert "create or restore" not in instruction.lower()

    def test_close_sprint_not_found_error(self, work_dir):
        """Missing sprint directory returns the existing not-found message."""
        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))

        assert result["status"] == "error"
        assert result["error"]["step"] == "precondition"
        assert "not found" in result["error"]["message"].lower()
        instruction = result["error"]["recovery"]["instruction"]
        assert "create or restore" in instruction.lower()
