"""Tests for clasi.tools.artifact_tools module."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clasi.tools.artifact_tools import (
    acquire_execution_lock,
    advance_sprint_phase,
    close_sprint,
    create_sprint,
    create_ticket,
    detail_sprint,
    get_sprint_status,
    insert_sprint,
    list_sprints,
    list_tickets,
    move_ticket_to_done,
    reconcile_worktrees,
    record_gate_result,
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
    """Set up a temporary working directory with .clasi/sprints/ structure."""
    _write_legacy_pin(tmp_path)
    monkeypatch.chdir(tmp_path)
    set_project(tmp_path)
    return tmp_path


def _advance_to_ticketing(work_dir, sprint_id: str) -> None:
    """Advance a sprint through review gates to ticketing phase for testing."""
    db_path = work_dir / ".clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # roadmap → planning-docs
    advance_phase(db_path, sprint_id)  # planning-docs → architecture-review
    record_gate(db_path, sprint_id, "architecture_review", "passed")
    advance_phase(db_path, sprint_id)  # architecture-review → ticketing (031/002)
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")


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
        """detail_sprint on a roadmap sprint scaffolds tickets/ and returns correct JSON."""
        create_sprint("My Sprint")
        result = json.loads(detail_sprint("001"))
        assert result["sprint_id"] == "001"
        assert result["phase"] == "planning-docs"
        # Single-doc model: only tickets/ and tickets/done/ are scaffolded —
        # no usecases.md/architecture-update.md (those are sprint.md sections).
        written_names = [Path(f).name for f in result["files_written"]]
        assert "usecases.md" not in written_names
        assert "architecture-update.md" not in written_names

    def test_scaffolds_full_directory_structure(self, work_dir):
        """After detail_sprint, tickets/ and tickets/done/ directories exist."""
        create_sprint("My Sprint")
        detail_sprint("001")
        sprint_dir = work_dir / ".clasi" / "sprints" / "001-my-sprint"
        assert not (sprint_dir / "usecases.md").exists()
        assert not (sprint_dir / "architecture-update.md").exists()
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
        """@clasi_tool (030/005) converts the domain ValueError into an
        {"ok": false, "error": ...} envelope instead of a raw MCP error."""
        result = json.loads(create_ticket("999", "Orphan"))
        assert result["ok"] is False
        assert "not found" in result["error"]["message"]

    def test_blocked_before_ticketing_phase(self, work_dir):
        """031/002: create_ticket checks the architecture_review gate result
        directly, not the sprint's phase -- a sprint that hasn't recorded
        that gate yet is rejected regardless of which phase it is in."""
        create_sprint("My Sprint")
        result = json.loads(create_ticket("001", "Too Early"))
        assert result["ok"] is False
        assert "architecture_review" in result["error"]["message"]

    def test_auto_links_single_sprint_issue_when_no_issue_param(self, work_dir):
        """create_ticket without issue param auto-links the sole sprint todo.

        Regression guard: the single-issue case is unambiguous and must keep
        auto-linking exactly as before.
        """
        create_sprint("My Sprint")
        _advance_to_ticketing(work_dir, "001")
        # Add a single-entry todos field to sprint.md frontmatter
        sprint_md = (
            work_dir / ".clasi" / "sprints" / "001-my-sprint" / "sprint.md"
        )
        fm = read_frontmatter(sprint_md)
        fm["todos"] = ["idea-a.md"]
        write_frontmatter(sprint_md, fm)

        result = json.loads(create_ticket("001", "Auto Linked"))
        ticket_fm = read_frontmatter(result["path"])
        assert ticket_fm["issue"] == "idea-a.md"

    def test_no_auto_link_when_sprint_has_multiple_issues(self, work_dir):
        """create_ticket without issue param does NOT auto-link when the
        sprint has 2+ linked issues — the ambiguous case must leave issue:
        empty rather than silently attaching every sprint issue.

        Uses a real multi-issue sprint fixture: two genuine issue files in
        the pending pool, linked to the sprint via link_sprint_issues (the
        real linkage path — mirrors this project's own sprint 020, which
        carries 9 linked issues this way), not a synthetic todos-only
        stand-in.
        """
        from clasi.tools.artifact_tools import link_sprint_issues

        create_sprint("My Sprint")
        _advance_to_ticketing(work_dir, "001")

        pending_issues_dir = work_dir / ".clasi" / "issues"
        pending_issues_dir.mkdir(parents=True, exist_ok=True)
        issue_a_path = pending_issues_dir / "issue-a.md"
        issue_b_path = pending_issues_dir / "issue-b.md"
        issue_a_path.write_text("---\nstatus: pending\n---\n\n# Issue A\n")
        issue_b_path.write_text("---\nstatus: pending\n---\n\n# Issue B\n")

        link_result = json.loads(
            link_sprint_issues("001", ["issue-a.md", "issue-b.md"])
        )
        assert link_result["linked"] == ["issue-a.md", "issue-b.md"]

        result = json.loads(create_ticket("001", "Unrelated Work"))
        ticket_fm = read_frontmatter(result["path"])

        # Never "all sprint issues" — issue: field must be absent/empty.
        assert not ticket_fm.get("issue")

        # Neither issue's tickets: backlink may have gained this ticket.
        # link_sprint_issues doesn't move issues out of the pending pool,
        # so they're still at their original paths.
        issue_a_fm = read_frontmatter(issue_a_path)
        issue_b_fm = read_frontmatter(issue_b_path)
        assert not issue_a_fm.get("tickets")
        assert not issue_b_fm.get("tickets")

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


class TestGateOrderAndAutoAdvance:
    """031/002: create_ticket checks architecture_review directly (not a
    phase index) and auto-advances to 'ticketing'; acquire_execution_lock
    checks stakeholder_approval before granting the lock and auto-advances
    to 'executing' -- neither requires a separate advance_sprint_phase
    call (SUC-002)."""

    def _advance_to_architecture_review(self, sprint_id: str) -> None:
        """planning-docs -> architecture-review, via the real tools --
        the part of the flow this ticket does not change."""
        detail_sprint(sprint_id)
        advance_sprint_phase(sprint_id)

    def test_create_ticket_reaches_ticketing_with_zero_rejected_calls(self, work_dir):
        """SUC-002 Main Flow, steps 1-3: record architecture_review, then
        create_ticket for the sprint's first ticket -- no
        advance_sprint_phase call to 'ticketing' in between, and the call
        is not rejected."""
        create_sprint("My Sprint")
        self._advance_to_architecture_review("001")
        record_gate_result("001", "architecture_review", "passed")

        result = json.loads(create_ticket("001", "First Ticket"))

        assert result.get("ok", True) is not False, result
        assert Path(result["path"]).exists()

        db_path = work_dir / ".clasi" / ".clasi.db"
        assert get_sprint_state(db_path, "001")["phase"] == "ticketing"

        sprint_md = work_dir / ".clasi" / "sprints" / "001-my-sprint" / "sprint.md"
        assert read_frontmatter(sprint_md).get("status") == "ticketing", (
            "DB phase and frontmatter status: must agree -- create_ticket's "
            "auto-advance mirrors frontmatter the same way "
            "Sprint.set_sprint_stage() does for every other phase write"
        )

    def test_create_ticket_second_call_does_not_move_phase_backward_or_error(self, work_dir):
        create_sprint("My Sprint")
        self._advance_to_architecture_review("001")
        record_gate_result("001", "architecture_review", "passed")
        create_ticket("001", "First Ticket")

        result = json.loads(create_ticket("001", "Second Ticket"))

        assert result.get("ok", True) is not False, result
        db_path = work_dir / ".clasi" / ".clasi.db"
        assert get_sprint_state(db_path, "001")["phase"] == "ticketing"

    def test_acquire_execution_lock_rejects_without_stakeholder_approval(self, work_dir):
        create_sprint("My Sprint")
        self._advance_to_architecture_review("001")
        record_gate_result("001", "architecture_review", "passed")
        create_ticket("001", "First Ticket")
        # Deliberately do NOT record stakeholder_approval.

        result = json.loads(acquire_execution_lock("001"))

        assert "error" in result
        assert "stakeholder_approval" in result["error"]
        db_path = work_dir / ".clasi" / ".clasi.db"
        assert get_sprint_state(db_path, "001")["lock"] is None
        assert get_sprint_state(db_path, "001")["phase"] == "ticketing"

    def test_acquire_execution_lock_grants_lock_and_advances_to_executing(
        self, work_dir, monkeypatch
    ):
        """SUC-002 Main Flow step 4: once stakeholder_approval is
        recorded, acquire_execution_lock grants the lock and the phase
        auto-advances to 'executing' with no separate
        advance_sprint_phase call."""
        from clasi.sprint import Sprint

        # Isolate this test from real git: create_branch() is exercised
        # by the git-backed lifecycle tests (test_sprint_lifecycle_
        # integration.py, test_design_overlay_lifecycle.py); this test's
        # point is the gate-check/auto-advance behavior, not branch
        # creation, and this file's work_dir fixture is not a git repo.
        monkeypatch.setattr(Sprint, "create_branch", lambda self: self.branch)

        create_sprint("My Sprint")
        self._advance_to_architecture_review("001")
        record_gate_result("001", "architecture_review", "passed")
        create_ticket("001", "First Ticket")
        record_gate_result("001", "stakeholder_approval", "skipped")

        result = json.loads(acquire_execution_lock("001"))

        assert "error" not in result, result
        assert result["reentrant"] is False
        assert result["branch"] == "sprint/001-my-sprint"

        db_path = work_dir / ".clasi" / ".clasi.db"
        state = get_sprint_state(db_path, "001")
        assert state["phase"] == "executing"
        assert state["lock"]["sprint_id"] == "001"

        sprint_md = work_dir / ".clasi" / "sprints" / "001-my-sprint" / "sprint.md"
        assert read_frontmatter(sprint_md).get("status") == "executing"

    def test_advance_to_failure_after_lock_granted_leaves_lock_held_and_retry_succeeds(
        self, work_dir, monkeypatch
    ):
        """Failure-mode contract: if advance_to() fails after
        db.acquire_lock() has already succeeded, the lock is NOT rolled
        back, the failure surfaces to the caller (never swallowed), and a
        retried acquire_execution_lock call completes the phase-advance
        -- db.acquire_lock()'s existing re-entrant path plus advance_to's
        own idempotency make the retry safe without re-checking the gate
        as a second safety measure or re-acquiring the lock."""
        import clasi.state_db_class as state_db_class_module
        from clasi.sprint import Sprint

        monkeypatch.setattr(Sprint, "create_branch", lambda self: self.branch)

        create_sprint("My Sprint")
        self._advance_to_architecture_review("001")
        record_gate_result("001", "architecture_review", "passed")
        create_ticket("001", "First Ticket")
        record_gate_result("001", "stakeholder_approval", "passed")

        real_advance_to = state_db_class_module.StateDB.advance_to
        calls = {"n": 0}

        def _flaky_advance_to(self, sprint_id, target_phase, required_gate=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ValueError("simulated advance_to failure")
            return real_advance_to(self, sprint_id, target_phase, required_gate)

        monkeypatch.setattr(state_db_class_module.StateDB, "advance_to", _flaky_advance_to)

        first = json.loads(acquire_execution_lock("001"))
        assert "error" in first, first
        assert "simulated advance_to failure" in first["error"]

        db_path = work_dir / ".clasi" / ".clasi.db"
        state = get_sprint_state(db_path, "001")
        assert state["lock"] is not None, "lock must not be rolled back"
        assert state["lock"]["sprint_id"] == "001"
        assert state["phase"] == "ticketing", "phase-advance failed, so phase is unchanged"

        second = json.loads(acquire_execution_lock("001"))

        assert "error" not in second, second
        assert second["reentrant"] is True

        state = get_sprint_state(db_path, "001")
        assert state["phase"] == "executing"
        assert calls["n"] == 2


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

    def test_unknown_sprint_id_returns_error_not_empty_list(self, work_dir):
        """sprint 030/005 (SUC-005): a typo'd/unknown sprint_id must return
        the uniform {"ok": false, "error": ...} envelope, not `[]` -- which
        looked exactly like "sprint exists, has no tickets"."""
        create_sprint("Sprint")
        result = json.loads(list_tickets(sprint_id="999"))
        assert result["ok"] is False
        assert "not found" in result["error"]["message"]


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
        result = json.loads(get_sprint_status("999"))
        assert result["ok"] is False
        assert "not found" in result["error"]["message"]

    def test_worktree_defaults_false(self, work_dir):
        create_sprint("Sprint")
        result = json.loads(get_sprint_status("001"))
        assert result["worktree"] is False

    def test_worktree_surfaces_true(self, work_dir):
        create_sprint("Sprint")
        sprint_md = work_dir / ".clasi" / "sprints" / "001-sprint" / "sprint.md"
        fm = read_frontmatter(sprint_md)
        fm["worktree"] = True
        write_frontmatter(sprint_md, fm)
        result = json.loads(get_sprint_status("001"))
        assert result["worktree"] is True


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
        result = json.loads(update_ticket_status(ticket["path"], "invalid"))
        assert result["ok"] is False
        assert "Invalid status" in result["error"]["message"]


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
        # The directory is still named done/ — only the declared status
        # changed (019-007, then 030/001). The two are independent.
        assert "done" in result["new_path"]
        assert not os.path.exists(result["old_path"])
        # Verify status was updated to the DB-phase vocabulary's terminal
        # value. 030/001: this asserted "closed" (the *computed
        # sprint-machine* vocabulary's terminal name, sprint 019-007's
        # choice) until archive() was changed to write "done" — the
        # DB-phase vocabulary's own terminal string, and the sole
        # vocabulary frontmatter now mirrors. See sprint 030's sprint.md
        # Design Rationale.
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

        result = json.loads(insert_sprint("001", "Urgent"))
        assert result["ok"] is False
        assert "cannot be renumbered" in result["error"]["message"]

    def test_insert_with_tickets_updates_references(self, work_dir):
        create_sprint("Alpha")
        create_sprint("Beta")
        _advance_to_ticketing(work_dir, "002")

        # Create tickets in Beta (002)
        create_ticket("002", "Task A")
        create_ticket("002", "Task B")

        # Now insert after Alpha — but Beta is in ticketing phase, should fail
        result = json.loads(insert_sprint("001", "Inserted"))
        assert result["ok"] is False
        assert "cannot be renumbered" in result["error"]["message"]

    def test_insert_after_nonexistent_sprint(self, work_dir):
        create_sprint("Alpha")
        result = json.loads(insert_sprint("999", "Ghost"))
        assert result["ok"] is False
        assert "not found" in result["error"]["message"]

    def test_new_sprint_has_full_structure(self, work_dir):
        """Single-doc model: insert_sprint writes only sprint.md (+ tickets dirs)."""
        create_sprint("Alpha")
        result = json.loads(insert_sprint("001", "New Sprint"))

        from pathlib import Path
        sprint_dir = Path(result["path"])
        assert (sprint_dir / "sprint.md").exists()
        assert not (sprint_dir / "usecases.md").exists()
        assert not (sprint_dir / "architecture-update.md").exists()
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
        # done/ is the archive directory name; "done" is the declared
        # status as of 030/001 (previously "closed", 019-007's choice —
        # see sprint 030's sprint.md Design Rationale).
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

    def test_close_does_not_copy_architecture_update(self, work_dir):
        """Single-doc model: close_sprint no longer copies architecture-update.md,

        even when a historical-shaped one is present on disk.
        """
        create_sprint("Sprint")
        sprint_dir = work_dir / ".clasi" / "sprints" / "001-sprint"
        # Write content to a historical-shaped architecture-update file
        arch_update = sprint_dir / "architecture-update.md"
        arch_update.write_text(
            "---\nsprint: '001'\nstatus: draft\n---\n\n# Update\n\nSome changes.\n",
            encoding="utf-8",
        )
        close_sprint("001")
        arch_dir = work_dir / ".clasi" / "architecture"
        dest = arch_dir / "architecture-update-001.md"
        assert not dest.exists()

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
        result = json.loads(close_sprint("999"))
        assert result["ok"] is False
        assert "not found" in result["error"]["message"]

    def test_close_destination_already_exists(self, work_dir):
        create_sprint("Sprint")
        done_dir = work_dir / ".clasi" / "sprints" / "done"
        done_dir.mkdir(parents=True)
        (done_dir / "001-sprint").mkdir()
        result = json.loads(close_sprint("001"))
        assert result["ok"] is False
        assert "already exists" in result["error"]["message"]


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
        result = json.loads(move_ticket_to_done("/nonexistent/ticket.md"))
        assert result["ok"] is False
        assert "not found" in result["error"]["message"]

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


class TestTicketStatusSingleWriter:
    """Frontmatter and directory location must agree after every status
    transition -- update_ticket_status(path, "done") and
    move_ticket_to_done both delegate to one combined primitive, and a
    stray plan file must not affect ticket counts (sprint 030 ticket
    003)."""

    def _assert_agree(self, path_str, expected_status, expected_in_done):
        fm = read_frontmatter(path_str)
        assert fm["status"] == expected_status
        assert (Path(path_str).parent.name == "done") == expected_in_done

    def test_full_round_trip_stays_in_agreement(self, work_dir):
        """open -> in-progress -> done -> reopen -> open: frontmatter and
        directory location agree after every single transition."""
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        path = ticket["path"]
        self._assert_agree(path, "open", False)

        result = json.loads(update_ticket_status(path, "in-progress"))
        self._assert_agree(result["path"], "in-progress", False)

        result = json.loads(update_ticket_status(result["path"], "done"))
        self._assert_agree(result["new_path"], "done", True)

        result = json.loads(reopen_ticket(result["new_path"]))
        self._assert_agree(result["new_path"], "open", False)

    def test_update_ticket_status_done_matches_move_ticket_to_done(self, work_dir):
        """No behavior divergence between the two entry points for a
        ticket already in the expected pre-state (open, still in
        tickets/)."""
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket_a = json.loads(create_ticket("001", "Task A"))
        ticket_b = json.loads(create_ticket("001", "Task B"))

        result_a = json.loads(update_ticket_status(ticket_a["path"], "done"))
        result_b = json.loads(move_ticket_to_done(ticket_b["path"]))

        assert Path(result_a["new_path"]).parent.name == "done"
        assert Path(result_b["new_path"]).parent.name == "done"
        assert read_frontmatter(result_a["new_path"])["status"] == "done"
        assert read_frontmatter(result_b["new_path"])["status"] == "done"

    def test_move_ticket_to_done_tolerant_after_update_already_moved(self, work_dir):
        """move_ticket_to_done, called on the pre-move path after
        update_ticket_status(path, "done") already moved the file, must
        not raise -- the compatibility contract a caller still invoking
        the two calls separately depends on."""
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        original_path = ticket["path"]

        update_ticket_status(original_path, "done")
        result = json.loads(move_ticket_to_done(original_path))

        assert Path(result["new_path"]).exists()
        assert Path(result["new_path"]).parent.name == "done"
        assert read_frontmatter(result["new_path"])["status"] == "done"

    def test_stray_plan_file_does_not_affect_list_tickets_count(self, work_dir):
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        plan_path = Path(ticket["path"]).parent / (Path(ticket["path"]).stem + "-plan.md")
        plan_path.write_text("---\ntitle: Plan\n---\n# Plan\n", encoding="utf-8")

        result = json.loads(list_tickets(sprint_id="001"))

        assert len(result) == 1


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
        """Nonexistent ticket returns an {"ok": false, "error": ...} envelope
        (sprint 030/005: @clasi_tool converts the domain ValueError)."""
        result = json.loads(reopen_ticket("/nonexistent/ticket.md"))
        assert result["ok"] is False
        assert "Ticket not found" in result["error"]["message"]

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

    def _mock_popen_ok(self, returncode=0, stdout="", stderr=""):
        """Popen-shaped mock for the "tests" step (032/006: close.py's
        _run_test_command uses subprocess.Popen, not subprocess.run, so
        the pytest-command call needs its own mock separate from
        mock_run's git-call side_effect list)."""
        proc = MagicMock()
        proc.communicate.return_value = (stdout, stderr)
        proc.returncode = returncode
        return proc

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

    @patch("clasi.worktree.cleanup_worktree")
    @patch("clasi.worktree.reconcile_worktrees")
    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_full_lifecycle_success(
        self, mock_popen, mock_run, mock_ver, mock_tag, mock_reconcile, mock_cleanup, work_dir
    ):
        """Full lifecycle returns structured success JSON, and orphaned ticket
        worktrees are swept: a merged-not-cleaned one is pruned, a
        failed/conflict one has its directory removed but branch retained
        and reported distinctly in worktrees_retained.
        """
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        # Create a ticket and move to done
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        # Mock subprocess calls: pytest, git config rebase.autoStash (version bump
        # prep), git add <archive paths + version file> (version bump), git commit
        # (version bump), git status --porcelain (.clasi.db guard, clean→no-op),
        # git rev-parse --verify branch (merge check), git merge-base --is-ancestor,
        # git rebase, git checkout master, git merge --no-ff, git push --tags,
        # git rev-parse --verify branch (delete check), git branch -d
        mock_popen.return_value = self._mock_popen_ok(0, "all tests passed")
        mock_run.side_effect = [
            self._make_subprocess_result(
                0, "# branch.oid deadbeef0000\n# branch.head master\n"
            ),  # git status --porcelain=v2 --branch (031/008 marker write)
            self._make_subprocess_result(0),  # git config rebase.autoStash (version bump prep)
            self._make_subprocess_result(0),  # git add <archive paths + version file> (version bump)
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
            self._make_subprocess_result(0, "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"),  # git worktree list --porcelain (no sprint-branch worktree)
        ]

        # Orphaned ticket worktree sweep (via reconcile_worktrees): one
        # merged-not-cleaned worktree (already fully cleaned up by
        # reconcile_worktrees itself) and one failed/conflict worktree
        # (left live by reconcile_worktrees, escalated for the caller to
        # decide — _prune_sprint_worktrees force-removes its directory and
        # retains its branch).
        mock_reconcile.return_value = {
            "cleaned": [
                {
                    "ticket_id": "002",
                    "path": "/repo/../worktree-001-002",
                    "branch": "ticket/001-002-merged-slug",
                    "reason": "merged-not-cleaned",
                }
            ],
            "escalated": [
                {
                    "ticket_id": "003",
                    "path": "/repo/../worktree-001-003",
                    "branch": "ticket/001-003-failed-slug",
                    "reason": "ambiguous audit state: failed",
                }
            ],
            "rogue": [],
        }

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "success"
        assert "done" in result["new_path"]
        assert result["git"]["merged"] is True
        assert result["git"]["merge_target"] == "master"
        assert result["git"]["branch_name"] == "sprint/001-sprint"

        # Merged-not-cleaned ticket worktree is reported as pruned.
        assert "/repo/../worktree-001-002" in result["worktrees_pruned"]

        # Failed/conflict ticket worktree: directory force-removed (branch
        # retained), reported distinctly in worktrees_retained rather than
        # worktrees_pruned/worktrees_failed.
        assert "/repo/../worktree-001-002" not in [
            r.get("path") for r in result.get("worktrees_retained", [])
        ]
        retained = result["worktrees_retained"]
        assert len(retained) == 1
        assert retained[0]["ticket_id"] == "003"
        assert retained[0]["path"] == "/repo/../worktree-001-003"
        assert retained[0]["branch"] == "ticket/001-003-failed-slug"
        mock_cleanup.assert_called_once_with(
            work_dir,
            Path("/repo/../worktree-001-003"),
            "ticket/001-003-failed-slug",
            keep_branch=True,
        )

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_version_bump_stages_explicit_paths_not_add_dash_a(
        self, mock_popen, mock_run, mock_ver, mock_tag, mock_reconcile, work_dir
    ):
        """027/002 regression: the version-bump commit must stage explicit
        paths -- the detected version file, plus the archived sprint
        directory's old/new location that Step 3 already produced -- via
        plain `git add <path>...`, never a blanket `git add -A` that
        would also sweep in whatever else happens to be sitting in the
        working tree (sprint 026's config/devices.json incident). It must
        also set `rebase.autoStash` so Step 6's real rebase (untouched by
        this ticket) tolerates any pre-existing dirty file this commit
        deliberately left out."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        pyproject = work_dir / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        mock_popen.return_value = self._mock_popen_ok(0, "all tests passed")
        mock_run.side_effect = [
            self._make_subprocess_result(
                0, "# branch.oid deadbeef0000\n# branch.head master\n"
            ),  # git status --porcelain=v2 --branch (031/008 marker write)
            self._make_subprocess_result(0),  # git config rebase.autoStash (version bump prep)
            self._make_subprocess_result(0),  # git add <archive paths + version file> (version bump)
            self._make_subprocess_result(0),  # git commit (version bump)
            self._make_subprocess_result(0, ""),  # git status --porcelain .clasi.db (clean)
            self._make_subprocess_result(1),  # git rev-parse --verify (merge: branch gone)
            self._make_subprocess_result(0),  # git push --tags
            self._make_subprocess_result(1),  # git rev-parse --verify (delete: branch gone)
            self._make_subprocess_result(0, "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"),  # git worktree list --porcelain
        ]
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "success"

        old_sprint_dir = str(work_dir / ".clasi" / "sprints" / "001-sprint")
        new_sprint_dir = str(work_dir / ".clasi" / "sprints" / "done" / "001-sprint")

        calls = mock_run.call_args_list
        add_calls = [c for c in calls if c.args[0][:2] == ["git", "add"]]
        # Exactly one `git add` in this run -- the .clasi.db guard is a
        # no-op here since `git status --porcelain` reports clean.
        assert len(add_calls) == 1, f"expected exactly one git add call, found {add_calls}"
        staged = add_calls[0].args[0][2:]
        assert staged == [old_sprint_dir, new_sprint_dir, str(pyproject)], (
            f"version bump must stage exactly the archive move and the "
            f"detected version file, got {staged}"
        )
        # No call anywhere in the lifecycle uses a blanket -A add.
        assert not any("-A" in c.args[0] for c in calls), (
            "version bump must never use `git add -A`"
        )
        config_calls = [
            c for c in calls
            if c.args[0] == ["git", "config", "rebase.autoStash", "true"]
        ]
        assert len(config_calls) == 1, (
            f"expected rebase.autoStash to be configured once, found {config_calls}"
        )

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("clasi.tools.artifact_tools.detect_version_file", return_value=None)
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_version_bump_stages_archive_move_but_no_file_when_none_detected(
        self, mock_popen, mock_run, mock_detect, mock_ver, mock_tag, mock_reconcile, work_dir
    ):
        """027/002 acceptance criterion (adjusted -- see ticket notes):
        when detect_version_file finds nothing, Step 5 must not call
        update_version_file or stage a version-file path. It still stages
        and commits the archived sprint directory's old/new location,
        though: Step 3's move is not itself part of this ticket's scope
        to change, and Step 6's real `git rebase` needs a working tree
        that's clean of at least tracked-and-committed-elsewhere changes
        (untracked/uncommitted files are separately handled by
        `rebase.autoStash`, covered by the sibling test above) -- so the
        commit this step makes is not purely conditional on a version
        file existing to bump."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        # Deliberately no pyproject.toml/package.json in work_dir.
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        mock_popen.return_value = self._mock_popen_ok(0, "all tests passed")
        mock_run.side_effect = [
            self._make_subprocess_result(
                0, "# branch.oid deadbeef0000\n# branch.head master\n"
            ),  # git status --porcelain=v2 --branch (031/008 marker write)
            self._make_subprocess_result(0),  # git config rebase.autoStash (version bump prep)
            self._make_subprocess_result(0),  # git add <archive paths only> (version bump)
            self._make_subprocess_result(0),  # git commit (version bump)
            self._make_subprocess_result(0, ""),  # git status --porcelain .clasi.db (clean)
            self._make_subprocess_result(1),  # git rev-parse --verify (merge: branch gone)
            self._make_subprocess_result(0),  # git push --tags
            self._make_subprocess_result(1),  # git rev-parse --verify (delete: branch gone)
            self._make_subprocess_result(0, "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"),  # git worktree list --porcelain
        ]
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "success", result

        old_sprint_dir = str(work_dir / ".clasi" / "sprints" / "001-sprint")
        new_sprint_dir = str(work_dir / ".clasi" / "sprints" / "done" / "001-sprint")

        calls = mock_run.call_args_list
        add_calls = [c for c in calls if c.args[0][:2] == ["git", "add"]]
        assert len(add_calls) == 1, f"expected exactly one git add call, found {add_calls}"
        staged = add_calls[0].args[0][2:]
        assert staged == [old_sprint_dir, new_sprint_dir], (
            f"with no version file detected, only the archive move should "
            f"be staged, got {staged}"
        )
        assert not any(p.endswith("pyproject.toml") or p.endswith("package.json") for p in staged), (
            f"no version-file path should be staged when none was detected, got {staged}"
        )

    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_test_failure_returns_error(self, mock_popen, mock_run, work_dir):
        """When tests fail, return structured error with recovery."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        # A failing test run: close_sprint returns from the "tests" step
        # before any git call, so mock_run (subprocess.run) is never
        # actually reached here -- only Popen (the pytest-command runner)
        # matters for this test.
        mock_popen.return_value = self._mock_popen_ok(
            1, "FAILED test_foo.py", "1 failed"
        )

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "error"
        assert result["error"]["step"] == "tests"
        assert "precondition_verification" in result["completed_steps"]
        assert "tests" not in result["completed_steps"]
        assert result["error"]["recovery"]["instruction"] is not None

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    def test_test_command_skip_sentinel_actually_skips_tests(
        self, mock_run, mock_ver, mock_tag, mock_reconcile, work_dir
    ):
        """sprint 030/005: test_command="SKIP" is the explicit, documented
        sentinel that actually skips the tests step -- replacing the
        unreachable test_command="" mechanism. Proven two ways: (1) no
        subprocess.run call is ever given pytest-shaped output/mocked as
        the test run (the side_effect list below has no "tests" entry at
        all -- if the tests step ran, the sequence would desync and the
        next assertion on git["merged"] would fail against the wrong mock
        result, or the side_effect iterator would raise StopIteration);
        (2) the "repairs" list names the "SKIP" sentinel explicitly.
        """
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        # No "pytest" entry -- the tests step must never call subprocess.run.
        mock_run.side_effect = [
            self._make_subprocess_result(0),  # git config rebase.autoStash (version bump prep)
            self._make_subprocess_result(0),  # git add <archive paths + version file> (version bump)
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
            self._make_subprocess_result(0, "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"),  # git worktree list --porcelain
        ]
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

        result = json.loads(
            close_sprint("001", branch_name="sprint/001-sprint", test_command="SKIP")
        )
        assert result["status"] == "success", result
        assert result["git"]["merged"] is True
        assert 'skipped tests (test_command is "SKIP")' in result["repairs"]

    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_merge_conflict_returns_error(self, mock_popen, mock_run, mock_ver, mock_tag, work_dir):
        """When merge has conflicts, return structured error."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        mock_popen.return_value = self._mock_popen_ok(0, "all tests passed")
        mock_run.side_effect = [
            self._make_subprocess_result(
                0, "# branch.oid deadbeef0000\n# branch.head master\n"
            ),  # git status --porcelain=v2 --branch (031/008 marker write)
            self._make_subprocess_result(0),  # git config rebase.autoStash (version bump prep)
            self._make_subprocess_result(0),  # git add <archive paths + version file> (version bump)
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

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_already_merged_branch_is_idempotent(
        self, mock_popen, mock_run, mock_ver, mock_tag, mock_reconcile, work_dir
    ):
        """If branch doesn't exist, merge step is skipped."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        mock_popen.return_value = self._mock_popen_ok(0, "all passed")
        mock_run.side_effect = [
            self._make_subprocess_result(
                0, "# branch.oid deadbeef0000\n# branch.head master\n"
            ),  # git status --porcelain=v2 --branch (031/008 marker write)
            self._make_subprocess_result(0),  # git config rebase.autoStash (version bump prep)
            self._make_subprocess_result(0),  # git add <archive paths + version file> (version bump)
            self._make_subprocess_result(0),  # git commit (version bump)
            self._make_subprocess_result(0, ""),  # git status --porcelain .clasi.db (clean)
            self._make_subprocess_result(1),  # git rev-parse --verify (branch gone, merge check)
            self._make_subprocess_result(0),  # git push --tags
            self._make_subprocess_result(1),  # git rev-parse --verify (branch gone, delete check)
            self._make_subprocess_result(0, "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"),  # git worktree list --porcelain
        ]
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

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

    def test_precondition_ticket_not_done_records_recovery_state(self, work_dir):
        """Regression guard (026/002): the ticket-not-done branch already
        wrote recovery state before this ticket touched the other two
        precondition branches, and must keep doing so unchanged."""
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "in-progress")

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["error"]["recovery"]["recorded"] is True
        assert result["error"]["recovery"]["allowed_paths"] == [ticket["path"]]

        db_path = work_dir / ".clasi" / ".clasi.db"
        recovery = get_recovery_state(db_path)
        assert recovery is not None
        assert recovery["step"] == "precondition"
        assert recovery["allowed_paths"] == [ticket["path"]]

    def test_frontmatter_fence_error_records_recovery_state(self, work_dir):
        """A broken opening '---' fence in sprint.md must write recovery
        state naming that exact file (026/002) -- previously this branch
        returned `recovery: {recorded: False, allowed_paths: []}`, a dead
        end the role-guard recovery bypass could never honor."""
        from clasi.state_db import init_db

        db_path = work_dir / ".clasi" / ".clasi.db"
        init_db(str(db_path))

        sprint_dir = work_dir / ".clasi" / "sprints" / "001-recovery-fence"
        sprint_dir.mkdir(parents=True)
        sprint_file = sprint_dir / "sprint.md"
        sprint_file.write_text(
            "--\nid: '001'\ntitle: Broken Fence\n---\n\n# Sprint 001\n",
            encoding="utf-8",
        )

        result = json.loads(
            close_sprint("001", branch_name="sprint/001-recovery-fence")
        )
        assert result["status"] == "error"
        assert result["error"]["step"] == "precondition"
        assert result["error"]["recovery"]["recorded"] is True
        assert result["error"]["recovery"]["allowed_paths"] == [str(sprint_file)]

        recovery = get_recovery_state(db_path)
        assert recovery is not None
        assert recovery["sprint_id"] == "001"
        assert recovery["step"] == "precondition"
        assert recovery["allowed_paths"] == [str(sprint_file)]

    def test_frontmatter_fence_error_recovery_permits_guarded_edit(self, work_dir):
        """After a fence-error close_sprint call, a guarded Edit of the
        exact sprint.md file named in the recovery instruction passes
        role-guard with reason 'recovery' -- the whole point of writing
        the recovery state. Real close_sprint + real handle_role_guard,
        no mocked recovery lookup. The target path lives under
        .clasi/sprints/ (role-guard's tier-0 block_prefixes), so an
        exit-0 result can only come from the recovery bypass."""
        from clasi.hook_handlers import handle_role_guard
        from clasi.state_db import init_db

        db_path = work_dir / ".clasi" / ".clasi.db"
        init_db(str(db_path))

        sprint_dir = work_dir / ".clasi" / "sprints" / "001-recovery-fence"
        sprint_dir.mkdir(parents=True)
        sprint_file = sprint_dir / "sprint.md"
        sprint_file.write_text(
            "--\nid: '001'\ntitle: Broken Fence\n---\n\n# Sprint 001\n",
            encoding="utf-8",
        )

        result = json.loads(
            close_sprint("001", branch_name="sprint/001-recovery-fence")
        )
        assert result["error"]["recovery"]["recorded"] is True

        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(sprint_file)},
            "session_id": "test-session-id",
        }
        with pytest.raises(SystemExit) as exc:
            handle_role_guard(payload)
        assert exc.value.code == 0

        hooks_log = work_dir / ".clasi" / "log" / "hooks.log"
        assert " recovery" in hooks_log.read_text(encoding="utf-8")

    def test_id_mismatch_error_records_recovery_state(self, work_dir):
        """A sprint.md whose 'id:' field doesn't match its directory must
        write recovery state naming that exact file (026/002)."""
        from clasi.state_db import init_db

        db_path = work_dir / ".clasi" / ".clasi.db"
        init_db(str(db_path))

        sprint_dir = work_dir / ".clasi" / "sprints" / "001-recovery-mismatch"
        sprint_dir.mkdir(parents=True)
        sprint_file = sprint_dir / "sprint.md"
        sprint_file.write_text(
            "---\nid: '999'\ntitle: Wrong Id\n---\n\n# Sprint 001\n",
            encoding="utf-8",
        )

        result = json.loads(
            close_sprint("001", branch_name="sprint/001-recovery-mismatch")
        )
        assert result["status"] == "error"
        assert result["error"]["step"] == "precondition"
        assert result["error"]["recovery"]["recorded"] is True
        assert result["error"]["recovery"]["allowed_paths"] == [str(sprint_file)]

        recovery = get_recovery_state(db_path)
        assert recovery is not None
        assert recovery["sprint_id"] == "001"
        assert recovery["step"] == "precondition"
        assert recovery["allowed_paths"] == [str(sprint_file)]

    def test_id_mismatch_error_recovery_permits_guarded_edit(self, work_dir):
        """After an id-mismatch close_sprint call, a guarded Edit of the
        exact sprint.md file named in the recovery instruction passes
        role-guard with reason 'recovery'. Real close_sprint + real
        handle_role_guard, no mocked recovery lookup."""
        from clasi.hook_handlers import handle_role_guard
        from clasi.state_db import init_db

        db_path = work_dir / ".clasi" / ".clasi.db"
        init_db(str(db_path))

        sprint_dir = work_dir / ".clasi" / "sprints" / "001-recovery-mismatch"
        sprint_dir.mkdir(parents=True)
        sprint_file = sprint_dir / "sprint.md"
        sprint_file.write_text(
            "---\nid: '999'\ntitle: Wrong Id\n---\n\n# Sprint 001\n",
            encoding="utf-8",
        )

        result = json.loads(
            close_sprint("001", branch_name="sprint/001-recovery-mismatch")
        )
        assert result["error"]["recovery"]["recorded"] is True

        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(sprint_file)},
            "session_id": "test-session-id",
        }
        with pytest.raises(SystemExit) as exc:
            handle_role_guard(payload)
        assert exc.value.code == 0

        hooks_log = work_dir / ".clasi" / "log" / "hooks.log"
        assert " recovery" in hooks_log.read_text(encoding="utf-8")

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_self_repair_moves_done_ticket(
        self, mock_popen, mock_run, mock_ver, mock_tag, mock_reconcile, work_dir
    ):
        """Ticket with done status but in tickets/ (not done/) gets moved."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        ticket = json.loads(create_ticket("001", "Task"))
        # Simulate frontmatter/directory drift directly. As of sprint 030
        # ticket 003, update_ticket_status(path, "done") performs the
        # tickets/done/ move in the same call, so this state (status: done,
        # still in tickets/) can no longer be produced through that tool --
        # write frontmatter directly (e.g. as if hand-edited) to exercise
        # close_sprint's self-repair path for a ticket that drifted some
        # other way.
        fm = read_frontmatter(ticket["path"])
        fm["status"] = "done"
        write_frontmatter(ticket["path"], fm)

        mock_popen.return_value = self._mock_popen_ok(0, "all passed")
        mock_run.side_effect = [
            self._make_subprocess_result(
                0, "# branch.oid deadbeef0000\n# branch.head master\n"
            ),  # git status --porcelain=v2 --branch (031/008 marker write)
            self._make_subprocess_result(0),  # git config rebase.autoStash (version bump prep)
            self._make_subprocess_result(0),  # git add <archive paths + version file> (version bump)
            self._make_subprocess_result(0),  # git commit (version bump)
            self._make_subprocess_result(0, ""),  # git status --porcelain .clasi.db (clean)
            self._make_subprocess_result(1),  # git rev-parse --verify (merge: branch gone)
            self._make_subprocess_result(0),  # git push --tags
            self._make_subprocess_result(1),  # git rev-parse --verify (delete: branch gone)
            self._make_subprocess_result(0, "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"),  # git worktree list --porcelain
        ]
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "success"
        assert any("moved ticket" in r for r in result["repairs"])

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_structured_result_format(
        self, mock_popen, mock_run, mock_ver, mock_tag, mock_reconcile, work_dir
    ):
        """Verify all expected fields in success result."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

        mock_popen.return_value = self._mock_popen_ok(0)
        mock_run.side_effect = [
            self._make_subprocess_result(
                0, "# branch.oid deadbeef0000\n# branch.head master\n"
            ),  # git status --porcelain=v2 --branch (031/008 marker write)
            self._make_subprocess_result(0),  # git config rebase.autoStash (version bump prep)
            self._make_subprocess_result(0),  # git add <archive paths + version file> (version bump)
            self._make_subprocess_result(0),  # git commit (version bump)
            self._make_subprocess_result(0, ""),  # git status --porcelain .clasi.db (clean)
            self._make_subprocess_result(1),  # git rev-parse --verify (merge: branch gone)
            self._make_subprocess_result(0),  # git push --tags
            self._make_subprocess_result(1),  # git rev-parse --verify (delete: branch gone)
            self._make_subprocess_result(0, "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"),  # git worktree list --porcelain
        ]
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

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

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_recovery_state_cleared_on_success(
        self, mock_popen, mock_run, mock_ver, mock_tag, mock_reconcile, work_dir
    ):
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

        mock_popen.return_value = self._mock_popen_ok(0)
        mock_run.side_effect = [
            self._make_subprocess_result(
                0, "# branch.oid deadbeef0000\n# branch.head master\n"
            ),  # git status --porcelain=v2 --branch (031/008 marker write)
            self._make_subprocess_result(0),  # git config rebase.autoStash (version bump prep)
            self._make_subprocess_result(0),  # git add <archive paths + version file> (version bump)
            self._make_subprocess_result(0),  # git commit (version bump)
            self._make_subprocess_result(0, ""),  # git status --porcelain .clasi.db (clean)
            self._make_subprocess_result(1),  # git rev-parse --verify (merge: branch gone)
            self._make_subprocess_result(0),  # git push --tags
            self._make_subprocess_result(1),  # git rev-parse --verify (delete: branch gone)
            self._make_subprocess_result(0, "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"),  # git worktree list --porcelain
        ]
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "success"

        # Recovery state should be cleared
        recovery = get_recovery_state(db_path)
        assert recovery is None


class TestCloseSprintTestTimeout:
    """Tests for the configurable test_timeout parameter (024-007).

    The old hardcoded 300s timeout produced false failures on this
    project's own ~460-525s suite. These tests exercise the resolution
    order (explicit param > .clasi/config.yaml test_timeout: key > 900s
    default) and the 0-means-unlimited sentinel, using a *real* (not
    mocked) subprocess for the test-command step so genuine timeout
    behavior is exercised. subprocess.run is NOT mocked here because the
    interesting behavior (a real TimeoutExpired) can only be observed
    with a real subprocess call; on timeout, close_sprint returns
    immediately from the tests step, so no later git/version steps run
    and nothing else needs mocking.
    """

    def _make_subprocess_result(self, returncode=0, stdout="", stderr=""):
        result = MagicMock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = stderr
        return result

    def _mock_popen_ok(self, returncode=0, stdout="", stderr=""):
        """Popen-shaped mock for the "tests" step (032/006: close.py's
        _run_test_command uses subprocess.Popen, not subprocess.run)."""
        proc = MagicMock()
        proc.communicate.return_value = (stdout, stderr)
        proc.returncode = returncode
        return proc

    def _setup_sprint(self, work_dir):
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )
        ticket = json.loads(create_ticket("001", "Task"))
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])

    def test_fast_command_closes_under_new_default(self, work_dir):
        """Regression: a fast test command still closes successfully now
        that the default timeout is 900s instead of 300s."""
        self._setup_sprint(work_dir)

        with patch("clasi.tools.artifact_tools.create_version_tag"), \
                patch(
                    "clasi.tools.artifact_tools.compute_next_version",
                    return_value="0.20260329.1",
                ), \
                patch("clasi.worktree.reconcile_worktrees") as mock_reconcile, \
                patch("subprocess.run") as mock_run, \
                patch("subprocess.Popen") as mock_popen:
            mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}
            mock_popen.return_value = self._mock_popen_ok(0)  # test_command="true"
            mock_run.side_effect = [
                self._make_subprocess_result(
                    0, "# branch.oid deadbeef0000\n# branch.head master\n"
                ),  # git status --porcelain=v2 --branch (031/008 marker write)
                self._make_subprocess_result(0),  # git config rebase.autoStash (version bump prep)
                self._make_subprocess_result(0),  # git add <archive paths + version file> (version bump)
                self._make_subprocess_result(0),  # git commit (version bump)
                self._make_subprocess_result(0, ""),  # git status --porcelain (clean)
                self._make_subprocess_result(1),  # git rev-parse --verify (merge: branch gone)
                self._make_subprocess_result(0),  # git push --tags
                self._make_subprocess_result(1),  # git rev-parse --verify (delete: branch gone)
                self._make_subprocess_result(
                    0, "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"
                ),  # git worktree list --porcelain
            ]

            result = json.loads(
                close_sprint("001", branch_name="sprint/001-sprint", test_command="true")
            )

        assert result["status"] == "success", f"Expected success, got: {result}"

    def test_slow_command_trips_low_explicit_timeout_and_names_value(self, work_dir):
        """A hung command with test_timeout explicitly set low (2s) still
        trips the timeout, blocks the close, and the error message names
        the configured value (not the old hardcoded 300)."""
        self._setup_sprint(work_dir)

        result = json.loads(
            close_sprint(
                "001",
                branch_name="sprint/001-sprint",
                test_command="sleep 30",
                test_timeout=2,
            )
        )

        assert result["status"] == "error"
        assert result["error"]["step"] == "tests"
        assert "2" in result["error"]["message"]
        assert "300" not in result["error"]["message"]
        assert "tests" not in result["completed_steps"]

    def test_config_key_used_when_no_explicit_param(self, work_dir):
        """A .clasi/config.yaml `test_timeout:` key is honored when the
        test_timeout parameter is not passed explicitly."""
        self._setup_sprint(work_dir)

        config_path = work_dir / ".clasi" / "config.yaml"
        existing = config_path.read_text(encoding="utf-8")
        config_path.write_text(existing + "\ntest_timeout: 2\n", encoding="utf-8")

        result = json.loads(
            close_sprint(
                "001",
                branch_name="sprint/001-sprint",
                test_command="sleep 30",
            )
        )

        assert result["status"] == "error"
        assert result["error"]["step"] == "tests"
        assert "2" in result["error"]["message"]

    def test_zero_timeout_means_unlimited_fast_command_completes(self, work_dir):
        """test_timeout=0 disables the timeout (passes timeout=None to
        Popen.communicate()); a fast command still completes normally."""
        self._setup_sprint(work_dir)

        with patch("clasi.tools.artifact_tools.create_version_tag"), \
                patch(
                    "clasi.tools.artifact_tools.compute_next_version",
                    return_value="0.20260329.1",
                ), \
                patch("clasi.worktree.reconcile_worktrees") as mock_reconcile, \
                patch("subprocess.run") as mock_run, \
                patch("subprocess.Popen") as mock_popen:
            mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}
            mock_popen.return_value = self._mock_popen_ok(0)  # test_command="true"
            mock_run.side_effect = [
                self._make_subprocess_result(
                    0, "# branch.oid deadbeef0000\n# branch.head master\n"
                ),  # git status --porcelain=v2 --branch (031/008 marker write)
                self._make_subprocess_result(0),  # git config rebase.autoStash (version bump prep)
                self._make_subprocess_result(0),  # git add <archive paths + version file> (version bump)
                self._make_subprocess_result(0),  # git commit (version bump)
                self._make_subprocess_result(0, ""),  # git status --porcelain (clean)
                self._make_subprocess_result(1),  # git rev-parse --verify (merge: branch gone)
                self._make_subprocess_result(0),  # git push --tags
                self._make_subprocess_result(1),  # git rev-parse --verify (delete: branch gone)
                self._make_subprocess_result(
                    0, "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"
                ),  # git worktree list --porcelain
            ]

            result = json.loads(
                close_sprint(
                    "001",
                    branch_name="sprint/001-sprint",
                    test_command="true",
                    test_timeout=0,
                )
            )

            # Confirm timeout=None was passed through to the test-command's
            # communicate() call (032/006: Popen.communicate(timeout=...),
            # not subprocess.run(..., timeout=...)).
            mock_popen.return_value.communicate.assert_called_once_with(timeout=None)

        assert result["status"] == "success", f"Expected success, got: {result}"


class TestReconcileWorktreesTool:
    """Tests for the reconcile_worktrees MCP tool (ticket 018-011)."""

    @patch("clasi.worktree.reconcile_worktrees")
    def test_returns_json_with_expected_shape_and_only_cleans_safe_worktrees(
        self, mock_reconcile, work_dir
    ):
        """The tool resolves sprint_dir/repo_root for the given sprint_id,
        delegates to clasi.worktree.reconcile_worktrees, and returns its
        cleaned/escalated/rogue result as JSON untouched. A mix of a
        safe-to-clean (merged-not-cleaned) worktree and an ambiguous
        (failed audit state) worktree is used to assert that only the
        safe one shows up in "cleaned" and the ambiguous one is reported,
        untouched, in "escalated".
        """
        create_sprint("Sprint")

        mock_reconcile.return_value = {
            "cleaned": [
                {
                    "ticket_id": "002",
                    "path": "/repo/../worktree-001-002",
                    "branch": "ticket/001-002-merged-slug",
                    "reason": "merged-not-cleaned",
                }
            ],
            "escalated": [
                {
                    "ticket_id": "003",
                    "path": "/repo/../worktree-001-003",
                    "branch": "ticket/001-003-failed-slug",
                    "reason": "ambiguous audit state: failed",
                }
            ],
            "rogue": [],
        }

        result = json.loads(reconcile_worktrees("001"))

        assert set(result.keys()) == {"cleaned", "escalated", "rogue"}
        assert len(result["cleaned"]) == 1
        assert result["cleaned"][0]["ticket_id"] == "002"
        assert result["cleaned"][0]["reason"] == "merged-not-cleaned"
        assert len(result["escalated"]) == 1
        assert result["escalated"][0]["ticket_id"] == "003"
        assert result["escalated"][0]["reason"] == "ambiguous audit state: failed"
        assert result["rogue"] == []

        # Verify the tool resolved sprint_dir/repo_root via the project and
        # passed them through to clasi.worktree.reconcile_worktrees.
        mock_reconcile.assert_called_once()
        call_args = mock_reconcile.call_args[0]
        repo_root_arg, sprint_dir_arg = call_args
        assert Path(repo_root_arg) == work_dir
        assert Path(sprint_dir_arg).name == "001-sprint"

    @patch("clasi.worktree.reconcile_worktrees")
    def test_unknown_sprint_id_returns_error_json_without_calling_reconcile(
        self, mock_reconcile, work_dir
    ):
        """An unresolvable sprint_id returns an error JSON payload and never
        reaches clasi.worktree.reconcile_worktrees."""
        result = json.loads(reconcile_worktrees("999"))

        assert "error" in result
        mock_reconcile.assert_not_called()


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

        # Verify only sprint.md + tickets dirs exist (single-doc model)
        sprint_dir = work_dir / ".clasi" / "sprints" / f"{sprint_id}-roundtrip-sprint"
        assert (sprint_dir / "sprint.md").exists()
        assert not (sprint_dir / "usecases.md").exists()
        assert not (sprint_dir / "architecture-update.md").exists()
        assert (sprint_dir / "tickets").is_dir()
        assert (sprint_dir / "tickets" / "done").is_dir()

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

    def test_list_sprints_finds_sprint_advanced_past_planning_docs(self, work_dir):
        """030/001: list_sprints(status=...) filters on the full DB-phase
        vocabulary, not just roadmap/planning-docs.

        Before this ticket, Sprint.advance_phase() only touched the DB —
        frontmatter status: was stuck at whatever detail_promote() last
        wrote ("planning-docs"), so list_sprints(status="ticketing")
        could never find a sprint actually at that phase.
        advance_sprint_phase now routes through Sprint.set_sprint_stage(),
        so frontmatter tracks every phase advance.
        """
        create_sprint("Sprint Alpha")  # 001
        detail_sprint("001")  # roadmap -> planning-docs

        # planning-docs -> architecture-review (no gate required)
        json.loads(advance_sprint_phase("001"))
        # architecture-review -> ticketing (needs architecture_review gate;
        # 031/002 deleted the stakeholder-review phase this used to step
        # through, and moved stakeholder_approval to gate
        # acquire_execution_lock instead — see this test file's
        # _advance_to_ticketing helper for the equivalent low-level path).
        record_gate_result("001", "architecture_review", "passed")
        result = json.loads(advance_sprint_phase("001"))
        assert result["new_phase"] == "ticketing"

        ticketing_sprints = json.loads(list_sprints(status="ticketing"))
        ticketing_ids = [s["id"] for s in ticketing_sprints]
        assert "001" in ticketing_ids

        # Not roadmap, not planning-docs — the mirrored value moved on.
        assert "001" not in [s["id"] for s in json.loads(list_sprints(status="roadmap"))]
        assert "001" not in [
            s["id"] for s in json.loads(list_sprints(status="planning-docs"))
        ]

        # And frontmatter itself carries the mirrored value.
        sprint_md = work_dir / ".clasi" / "sprints" / "001-sprint-alpha" / "sprint.md"
        fm = read_frontmatter(sprint_md)
        assert fm.get("status") == "ticketing"


class TestCloseSprintLockAndDbGuard:
    """Tests for .clasi.db commit guard (step 5b) and lock release on merge failure."""

    def _make_subprocess_result(self, returncode=0, stdout="", stderr=""):
        result = MagicMock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = stderr
        return result

    def _mock_popen_ok(self, returncode=0, stdout="", stderr=""):
        """Popen-shaped mock for the "tests" step (032/006: close.py's
        _run_test_command uses subprocess.Popen, not subprocess.run)."""
        proc = MagicMock()
        proc.communicate.return_value = (stdout, stderr)
        proc.returncode = returncode
        return proc

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_dirty_db_guard_commits_when_versioning_disabled(
        self, mock_popen, mock_run, mock_reconcile, work_dir
    ):
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
        mock_popen.return_value = self._mock_popen_ok(0, "")  # pytest (pass)
        mock_run.side_effect = [
            self._make_subprocess_result(
                0, "# branch.oid deadbeef0000\n# branch.head master\n"
            ),  # git status --porcelain=v2 --branch (031/008 marker write)
            self._make_subprocess_result(0, " M .clasi/.clasi.db\n"),  # git status --porcelain (dirty)
            self._make_subprocess_result(0, "sprint/001-sprint\n"),  # git rev-parse --abbrev-ref HEAD
            self._make_subprocess_result(0),            # git add .clasi.db
            self._make_subprocess_result(0),            # git commit
            self._make_subprocess_result(1),            # git rev-parse --verify (branch gone)
            self._make_subprocess_result(1),            # git rev-parse --verify (delete, branch gone)
            self._make_subprocess_result(0, "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"),  # git worktree list --porcelain
        ]
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result["status"] == "success"

        # Verify that git add and git commit were called with the .clasi.db path
        calls = mock_run.call_args_list
        db_path_str = str(work_dir / ".clasi" / ".clasi.db")
        add_calls = [c for c in calls if c.args[0][:2] == ["git", "add"] and db_path_str in c.args[0]]
        commit_calls = [c for c in calls if c.args[0][:3] == ["git", "commit", "-m"] and "chore: update .clasi.db" in c.args[0]]
        assert len(add_calls) == 1, "Expected one git add .clasi.db call"
        assert len(commit_calls) == 1, "Expected one git commit chore: update .clasi.db call"

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260329.1")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_dirty_db_guard_is_noop_when_versioning_cleans_it(
        self, mock_popen, mock_run, mock_ver, mock_tag, mock_reconcile, work_dir
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
        # pytest, git config rebase.autoStash (version bump prep),
        # git add <archive paths + version file> (version bump), git commit
        # (version bump), git status --porcelain (empty = clean, guard is no-op),
        # git rev-parse --verify (branch gone), git push --tags, git rev-parse --verify (delete)
        mock_popen.return_value = self._mock_popen_ok(0)  # pytest
        mock_run.side_effect = [
            self._make_subprocess_result(
                0, "# branch.oid deadbeef0000\n# branch.head master\n"
            ),  # git status --porcelain=v2 --branch (031/008 marker write)
            self._make_subprocess_result(0),        # git config rebase.autoStash (version bump prep)
            self._make_subprocess_result(0),        # git add <archive paths + version file> (version bump)
            self._make_subprocess_result(0),        # git commit (version bump)
            self._make_subprocess_result(0, ""),    # git status --porcelain (clean)
            self._make_subprocess_result(1),        # git rev-parse --verify (branch gone)
            self._make_subprocess_result(0),        # git push --tags
            self._make_subprocess_result(1),        # git rev-parse --verify (delete, gone)
            self._make_subprocess_result(0, "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"),  # git worktree list --porcelain
        ]
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

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
    @patch("subprocess.Popen")
    def test_lock_released_after_merge_failure(self, mock_popen, mock_run, work_dir):
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
        mock_popen.return_value = self._mock_popen_ok(0, "")  # pytest (pass)
        mock_run.side_effect = [
            self._make_subprocess_result(
                0, "# branch.oid deadbeef0000\n# branch.head master\n"
            ),  # git status --porcelain=v2 --branch (031/008 marker write)
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

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_db_guard_skipped_when_not_on_sprint_branch(
        self, mock_popen, mock_run, mock_reconcile, work_dir
    ):
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
        mock_popen.return_value = self._mock_popen_ok(0, "")  # pytest (pass)
        mock_run.side_effect = [
            self._make_subprocess_result(
                0, "# branch.oid deadbeef0000\n# branch.head master\n"
            ),  # git status --porcelain=v2 --branch (031/008 marker write)
            self._make_subprocess_result(0, " M .clasi/.clasi.db\n"),  # git status --porcelain (dirty)
            self._make_subprocess_result(0, "master\n"),  # git rev-parse --abbrev-ref HEAD (wrong branch)
            # Guard skipped — no git add or git commit for .clasi.db
            self._make_subprocess_result(1),            # git rev-parse --verify (branch gone)
            self._make_subprocess_result(1),            # git rev-parse --verify (delete, branch gone)
            self._make_subprocess_result(0, "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"),  # git worktree list --porcelain
        ]
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

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
