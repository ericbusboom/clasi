"""System tests for the full exception flow.

Tests cover:
- throw_ticket_exception followed by list_tickets(status="exception")
- review_sprint_pre_close blocks when a ticket has status: exception
"""

import json
from pathlib import Path

import pytest

from clasi.tools.artifact_tools import (
    create_sprint,
    create_ticket,
    list_tickets,
    review_sprint_pre_close,
    throw_ticket_exception,
    update_ticket_status,
)
from clasi.mcp_server import set_project
from clasi.state_db import (
    acquire_lock,
    advance_phase,
    record_gate,
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


class TestThrowAndList:
    """System test: throw exception then assert list_tickets finds it."""

    def test_throw_and_list(self, work_dir):
        """Create a sprint + ticket, throw exception, assert list_tickets returns it."""
        create_sprint("Exception Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Blocked Task"))
        ticket_path = ticket["path"]

        # Set to in-progress first (realistic scenario)
        update_ticket_status(ticket_path, "in-progress")

        # Throw the exception
        throw_result = json.loads(
            throw_ticket_exception(
                ticket_path,
                thrown_by="programmer",
                attempted="implemented the blocked feature",
                conflict="architecture-update.md §2 — requires missing component",
                surface="internal",
            )
        )
        assert throw_result["new_status"] == "exception"

        # list_tickets(status="exception") must return that ticket
        exception_tickets = json.loads(list_tickets(status="exception"))
        assert len(exception_tickets) == 1
        assert exception_tickets[0]["id"] == "001"
        assert exception_tickets[0]["status"] == "exception"
        assert exception_tickets[0]["sprint_id"] == "001"

    def test_throw_does_not_appear_in_open_or_done(self, work_dir):
        """After throwing, the ticket does not appear in open or done listings."""
        create_sprint("Exception Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Blocked Task"))

        throw_ticket_exception(
            ticket["path"],
            thrown_by="programmer",
            attempted="x",
            conflict="y",
            surface="internal",
        )

        open_tickets = json.loads(list_tickets(status="open"))
        done_tickets = json.loads(list_tickets(status="done"))
        assert len(open_tickets) == 0
        assert len(done_tickets) == 0

    def test_unfiltered_list_includes_exception_ticket(self, work_dir):
        """list_tickets() with no status filter returns exception tickets too."""
        create_sprint("Exception Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Blocked Task"))

        throw_ticket_exception(
            ticket["path"],
            thrown_by="programmer",
            attempted="x",
            conflict="y",
            surface="internal",
        )

        all_tickets = json.loads(list_tickets())
        assert any(t["status"] == "exception" for t in all_tickets)


class TestExceptionTicketBlocksPreClose:
    """System test: review_sprint_pre_close returns error when exception ticket exists."""

    def test_exception_ticket_blocks_pre_close(self, work_dir):
        """review_sprint_pre_close returns not-passed when a ticket has status: exception."""
        create_sprint("Blocked Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Problematic Task"))
        ticket_path = ticket["path"]

        throw_ticket_exception(
            ticket_path,
            thrown_by="programmer",
            attempted="tried to implement the feature",
            conflict="incompatible dependency discovered",
            surface="user-visible",
        )

        result = json.loads(review_sprint_pre_close("001"))
        assert result["passed"] is False

    def test_exception_ticket_issue_listed(self, work_dir):
        """review_sprint_pre_close includes an issue for the exception-status ticket."""
        create_sprint("Blocked Sprint")
        _advance_to_ticketing(work_dir, "001")
        ticket = json.loads(create_ticket("001", "Problematic Task"))

        throw_ticket_exception(
            ticket["path"],
            thrown_by="programmer",
            attempted="tried X",
            conflict="blocked by Y",
            surface="internal",
        )

        result = json.loads(review_sprint_pre_close("001"))
        assert result["passed"] is False
        # The exception ticket's status is "exception", not "done"
        ticket_done_issues = [
            i for i in result["issues"] if i["check"] == "ticket_done"
        ]
        assert len(ticket_done_issues) >= 1

    def test_mixed_tickets_exception_still_blocks(self, work_dir):
        """A sprint with one done and one exception ticket fails pre-close."""
        create_sprint("Mixed Sprint")
        _advance_to_ticketing(work_dir, "001")

        # Both tickets are in sprint "001"; ticket IDs are per-sprint (001, 002)
        ticket1 = json.loads(create_ticket("001", "Done Task"))
        ticket2 = json.loads(create_ticket("001", "Exception Task"))

        # Complete ticket 1
        update_ticket_status(ticket1["path"], "done")

        # Throw exception on ticket 2
        throw_ticket_exception(
            ticket2["path"],
            thrown_by="programmer",
            attempted="attempted implementation",
            conflict="fundamental conflict",
            surface="internal",
        )

        result = json.loads(review_sprint_pre_close("001"))
        assert result["passed"] is False
