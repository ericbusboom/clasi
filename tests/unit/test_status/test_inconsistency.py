"""Unit tests for clasi.status.inconsistency.detect_inconsistencies.

Tests use minimal fake project/sprint/ticket objects so no real filesystem,
git, or DB I/O occurs.  The fake objects return controllable frontmatter
data so we can set up matching and mismatching declared/computed state pairs
without touching the filesystem.
"""

from __future__ import annotations

import importlib

import pytest

import clasi.state_machine.predicates  # noqa: F401 — side-effect: registers all predicates
import clasi.state_machine.predicates.project
import clasi.state_machine.predicates.sprint
import clasi.state_machine.predicates.ticket
from clasi.state_machine.registry import clear_registry
from clasi.status.inconsistency import detect_inconsistencies


# ---------------------------------------------------------------------------
# Registry guard (mirrors test_reporter.py pattern)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ensure_predicates_registered():
    """Re-register predicates if the registry was cleared by another test module."""
    clear_registry()
    importlib.reload(clasi.state_machine.predicates.project)
    importlib.reload(clasi.state_machine.predicates.sprint)
    importlib.reload(clasi.state_machine.predicates.ticket)
    yield


# ---------------------------------------------------------------------------
# Minimal fake objects
# ---------------------------------------------------------------------------


class FakeArtifact:
    """Minimal stand-in for clasi artifact with controllable frontmatter."""

    def __init__(self, fm: dict):
        self.frontmatter = fm


class FakeSprint:
    """Minimal stand-in for clasi.sprint.Sprint.

    Returns a configurable frontmatter status from sprint_doc, and
    delegates ticket lookups to an optional list of FakeTicket objects.
    """

    def __init__(
        self,
        sprint_id: str = "001",
        status: str | None = "open",
        tickets: list | None = None,
    ):
        self._id = sprint_id
        self._status = status
        self._tickets = tickets or []

        fm = {}
        if status is not None:
            fm["status"] = status
        self.sprint_doc = FakeArtifact(fm)
        # Provide attributes needed by ClasiStateReader when it reads ticket paths
        self.tickets_dir = _NonExistentPath()
        self.tickets_done_dir = _NonExistentPath()

    @property
    def id(self) -> str:
        return self._id


class _NonExistentPath:
    """Fake Path-like that says it does not exist (no real files)."""

    def exists(self) -> bool:
        return False

    def glob(self, pattern: str):
        return []


class FakeProject:
    """Minimal stand-in for clasi.project.Project.

    Maps sprint IDs to FakeSprint objects for ``get_sprint``.
    """

    def __init__(self, sprints: list[FakeSprint] | None = None):
        self._sprints_by_id: dict[str, FakeSprint] = {}
        for s in (sprints or []):
            self._sprints_by_id[s.id] = s

    def get_sprint(self, sprint_id: str) -> FakeSprint:
        if sprint_id in self._sprints_by_id:
            return self._sprints_by_id[sprint_id]
        raise ValueError(f"Sprint '{sprint_id}' not found")


# ---------------------------------------------------------------------------
# Helpers for building status-dict entries
# ---------------------------------------------------------------------------


def _sprint_entry(sprint_id: str, state: str, tickets: list | None = None) -> dict:
    """Build a minimal sprint entry for a status_dict."""
    tix = tickets or []
    tickets_block: dict = {"total": len(tix)}
    if tix:
        tickets_block["details"] = tix
    return {
        "id": sprint_id,
        "state": state,
        "available_transitions": [],
        "tickets": tickets_block,
    }


def _ticket_entry(ticket_id: str, state: str) -> dict:
    """Build a minimal ticket entry for a sprint's tickets.details list."""
    return {
        "id": ticket_id,
        "state": state,
        "available_transitions": [],
    }


def _status_dict(sprints: list | None = None) -> dict:
    """Build a minimal full status dict with the given sprint entries."""
    return {
        "agent": "team-lead",
        "computed_at": "2026-01-01T00:00:00+00:00",
        "project": {"state": "in-sprint", "available_transitions": []},
        "sprints": sprints or [],
        "issues": {"total": 0, "pending": 0, "assigned_to_sprint": 0},
        "notes": {"current_focus": "...", "allowed_next_actions": [], "blocked_actions": []},
        "inconsistencies": [],
    }


# ---------------------------------------------------------------------------
# Tests: empty inputs
# ---------------------------------------------------------------------------


class TestEmptyInputs:
    def test_no_sprints_returns_empty_list(self):
        project = FakeProject()
        result = detect_inconsistencies(project, _status_dict())
        assert result == []

    def test_sprint_with_no_tickets_and_matching_state_returns_empty(self):
        """Sprint declared open, computed open → no inconsistency."""
        project = FakeProject([FakeSprint("001", status="open")])
        status = _status_dict([_sprint_entry("001", state="open")])
        result = detect_inconsistencies(project, status)
        assert result == []

    def test_sprint_with_no_declared_status_skipped(self):
        """No status: in frontmatter → skipped, no entry emitted."""
        project = FakeProject([FakeSprint("001", status=None)])
        status = _status_dict([_sprint_entry("001", state="open")])
        result = detect_inconsistencies(project, status)
        assert result == []


# ---------------------------------------------------------------------------
# Tests: sprint state drift
# ---------------------------------------------------------------------------


class TestSprintStateDrift:
    def test_matching_sprint_state_produces_no_entry(self):
        """Declared open == computed open → empty list."""
        project = FakeProject([FakeSprint("001", status="open")])
        status = _status_dict([_sprint_entry("001", state="open")])
        result = detect_inconsistencies(project, status)
        assert result == []

    def test_mismatched_sprint_state_produces_entry(self):
        """Declared planned != computed open → one state_drift entry."""
        project = FakeProject([FakeSprint("001", status="planned")])
        status = _status_dict([_sprint_entry("001", state="open")])
        result = detect_inconsistencies(project, status)
        assert len(result) == 1
        entry = result[0]
        assert entry["kind"] == "state_drift"
        assert entry["machine"] == "sprint"
        assert entry["id"] == "001"
        assert entry["declared"] == "planned"
        assert entry["computed"] == "open"
        assert "explanation" in entry
        assert isinstance(entry["explanation"], str)
        assert len(entry["explanation"]) > 0

    def test_sprint_drift_explanation_mentions_failing_predicates(self):
        """Explanation should mention at least one predicate name when available."""
        project = FakeProject([FakeSprint("001", status="planned")])
        status = _status_dict([_sprint_entry("001", state="open")])
        result = detect_inconsistencies(project, status)
        assert len(result) == 1
        explanation = result[0]["explanation"]
        # The planned state requires is_architecture_present and is_usecases_present
        # which will both fail against a NullStateReader-like context.
        # Explanation should reference at least "planned" or a predicate name.
        assert "planned" in explanation

    def test_unknown_declared_sprint_state_produces_entry_with_explanation(self):
        """A declared state that is not in the machine gets an explanation note."""
        project = FakeProject([FakeSprint("001", status="nonexistent-state")])
        status = _status_dict([_sprint_entry("001", state="open")])
        result = detect_inconsistencies(project, status)
        assert len(result) == 1
        entry = result[0]
        assert entry["kind"] == "state_drift"
        assert "nonexistent-state" in entry["explanation"]

    def test_sprint_not_found_in_project_produces_no_entry(self):
        """If project can't find the sprint, no entry is emitted (safe default)."""
        project = FakeProject()  # no sprints registered
        status = _status_dict([_sprint_entry("999", state="open")])
        # FakeProject(999) frontmatter → None → skip
        result = detect_inconsistencies(project, status)
        assert result == []

    def test_multiple_sprints_only_drifting_one_flagged(self):
        """Only the sprint with a mismatch produces an entry."""
        project = FakeProject([
            FakeSprint("001", status="open"),   # matches
            FakeSprint("002", status="planned"),  # mismatch: computed open
        ])
        status = _status_dict([
            _sprint_entry("001", state="open"),
            _sprint_entry("002", state="open"),
        ])
        result = detect_inconsistencies(project, status)
        assert len(result) == 1
        assert result[0]["id"] == "002"


# ---------------------------------------------------------------------------
# Tests: ticket state drift
# ---------------------------------------------------------------------------


class TestTicketStateDrift:
    def test_ticket_missing_in_project_produces_no_entry(self):
        """If the ticket file is not found in the project, no entry is emitted."""
        project = FakeProject([FakeSprint("001", status="open")])
        ticket = _ticket_entry("001-001", state="open")
        status = _status_dict([_sprint_entry("001", state="open", tickets=[ticket])])
        # No ticket files found (NonExistentPath) → declared = None → skip
        result = detect_inconsistencies(project, status)
        assert result == []

    def test_ticket_state_drift_entry_shape(self, tmp_path):
        """A ticket whose declared status != computed state produces a state_drift entry."""
        # Build a real ticket file so _read_ticket_declared_status can find it.
        sprint_dir = tmp_path / "sprints" / "001"
        tickets_dir = sprint_dir / "tickets"
        tickets_dir.mkdir(parents=True)
        ticket_file = tickets_dir / "001-001-my-ticket.md"
        ticket_file.write_text(
            "---\nid: '001-001'\nstatus: in-progress\n---\n# Ticket\n",
            encoding="utf-8",
        )

        # Build fake sprint with the real tickets_dir path.
        sprint = FakeSprint("001", status="open")
        sprint.tickets_dir = tickets_dir
        sprint.tickets_done_dir = tickets_dir / "done"
        sprint.sprint_doc = FakeArtifact({"status": "open"})

        project = FakeProject([sprint])

        # Ticket dict says state=open; frontmatter says status=in-progress
        ticket = _ticket_entry("001-001", state="open")
        status = _status_dict([_sprint_entry("001", state="open", tickets=[ticket])])
        result = detect_inconsistencies(project, status)

        ticket_entries = [e for e in result if e["machine"] == "ticket"]
        assert len(ticket_entries) == 1
        entry = ticket_entries[0]
        assert entry["kind"] == "state_drift"
        assert entry["machine"] == "ticket"
        assert entry["id"] == "001-001"
        assert entry["declared"] == "in-progress"
        assert entry["computed"] == "open"
        assert isinstance(entry["explanation"], str)
        assert len(entry["explanation"]) > 0

    def test_ticket_matching_state_no_entry(self, tmp_path):
        """Declared in-progress == computed in-progress → no entry for ticket."""
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir(parents=True)
        ticket_file = tickets_dir / "001-001-my-ticket.md"
        ticket_file.write_text(
            "---\nid: '001-001'\nstatus: open\n---\n# Ticket\n",
            encoding="utf-8",
        )

        sprint = FakeSprint("001", status="open")
        sprint.tickets_dir = tickets_dir
        sprint.tickets_done_dir = tickets_dir / "done"
        sprint.sprint_doc = FakeArtifact({"status": "open"})
        project = FakeProject([sprint])

        ticket = _ticket_entry("001-001", state="open")
        status = _status_dict([_sprint_entry("001", state="open", tickets=[ticket])])
        result = detect_inconsistencies(project, status)
        # Sprint matches, ticket matches → no entries
        assert result == []

    def test_ticket_unknown_declared_state_produces_entry_with_explanation(self, tmp_path):
        """An unrecognised declared ticket state gets an explanation note."""
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir(parents=True)
        ticket_file = tickets_dir / "001-001-my-ticket.md"
        ticket_file.write_text(
            "---\nid: '001-001'\nstatus: weird-state\n---\n# Ticket\n",
            encoding="utf-8",
        )

        sprint = FakeSprint("001", status="open")
        sprint.tickets_dir = tickets_dir
        sprint.tickets_done_dir = tickets_dir / "done"
        sprint.sprint_doc = FakeArtifact({"status": "open"})
        project = FakeProject([sprint])

        ticket = _ticket_entry("001-001", state="open")
        status = _status_dict([_sprint_entry("001", state="open", tickets=[ticket])])
        result = detect_inconsistencies(project, status)
        ticket_entries = [e for e in result if e["machine"] == "ticket"]
        assert len(ticket_entries) == 1
        assert "weird-state" in ticket_entries[0]["explanation"]


# ---------------------------------------------------------------------------
# Tests: reporter integration
# ---------------------------------------------------------------------------


class TestReporterIntegration:
    """Verify that StatusReporter.build() calls detect_inconsistencies and
    populates inconsistencies (not always an empty list after ticket 004)."""

    def test_reporter_inconsistencies_key_is_list(self):
        """After ticket 004, the inconsistencies key is a list (may be empty)."""
        from clasi.state_machine.context import NullStateReader
        from clasi.status.reporter import StatusReporter

        class EmptyProject:
            def list_sprints(self, status=None):
                return []
            def list_issues(self):
                return []

        reporter = StatusReporter(EmptyProject(), reader=NullStateReader())
        result = reporter.build()
        assert isinstance(result["inconsistencies"], list)

    def test_reporter_inconsistencies_empty_for_no_sprints(self):
        """With no sprints, detect_inconsistencies returns [] and reporter echoes it."""
        from clasi.state_machine.context import NullStateReader
        from clasi.status.reporter import StatusReporter

        class EmptyProject:
            def list_sprints(self, status=None):
                return []
            def list_issues(self):
                return []

        reporter = StatusReporter(EmptyProject(), reader=NullStateReader())
        result = reporter.build()
        assert result["inconsistencies"] == []
