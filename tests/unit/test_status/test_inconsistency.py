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
from clasi.project import Project
from clasi.sprint import Sprint


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


class FakeStateDB:
    """Minimal stand-in for clasi.state_db_class.StateDB (030/001).

    Maps sprint IDs to a DB phase string. ``get_sprint_state`` mirrors
    the real StateDB's contract of raising ValueError for an
    unregistered sprint, which _read_sprint_db_phase (inconsistency.py)
    catches and treats as "no signal to compare" (fail-open).
    """

    def __init__(self, phases: dict[str, str] | None = None):
        self._phases = dict(phases or {})

    def get_sprint_state(self, sprint_id: str) -> dict:
        if sprint_id not in self._phases:
            raise ValueError(f"Sprint '{sprint_id}' is not registered")
        return {"phase": self._phases[sprint_id]}


class FakeProject:
    """Minimal stand-in for clasi.project.Project.

    Maps sprint IDs to FakeSprint objects for ``get_sprint``, and exposes
    a ``.db`` (FakeStateDB) for the DB-phase side of the sprint-level
    drift comparison (030/001).
    """

    def __init__(
        self,
        sprints: list[FakeSprint] | None = None,
        phases: dict[str, str] | None = None,
    ):
        self._sprints_by_id: dict[str, FakeSprint] = {}
        for s in (sprints or []):
            self._sprints_by_id[s.id] = s
        self.db = FakeStateDB(phases)

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

    def test_sprint_with_no_tickets_and_matching_phase_returns_empty(self):
        """Declared frontmatter status == DB phase → no inconsistency."""
        project = FakeProject(
            [FakeSprint("001", status="ticketing")],
            phases={"001": "ticketing"},
        )
        status = _status_dict([_sprint_entry("001", state="open")])
        result = detect_inconsistencies(project, status)
        assert result == []

    def test_sprint_with_no_declared_status_skipped(self):
        """No status: in frontmatter → skipped, no entry emitted."""
        project = FakeProject(
            [FakeSprint("001", status=None)], phases={"001": "ticketing"}
        )
        status = _status_dict([_sprint_entry("001", state="open")])
        result = detect_inconsistencies(project, status)
        assert result == []


# ---------------------------------------------------------------------------
# Tests: sprint stage drift (030/001: DB phase vs frontmatter status)
# ---------------------------------------------------------------------------


class TestSprintStateDrift:
    def test_matching_sprint_phase_produces_no_entry(self):
        """Declared ticketing == DB phase ticketing → empty list."""
        project = FakeProject(
            [FakeSprint("001", status="ticketing")],
            phases={"001": "ticketing"},
        )
        status = _status_dict([_sprint_entry("001", state="open")])
        result = detect_inconsistencies(project, status)
        assert result == []

    def test_mismatched_sprint_phase_produces_entry(self):
        """Declared planning-docs != DB phase ticketing → one state_drift entry."""
        project = FakeProject(
            [FakeSprint("001", status="planning-docs")],
            phases={"001": "ticketing"},
        )
        status = _status_dict([_sprint_entry("001", state="open")])
        result = detect_inconsistencies(project, status)
        assert len(result) == 1
        entry = result[0]
        assert entry["kind"] == "state_drift"
        assert entry["machine"] == "sprint"
        assert entry["id"] == "001"
        assert entry["declared"] == "planning-docs"
        assert entry["computed"] == "ticketing"
        assert "explanation" in entry
        assert isinstance(entry["explanation"], str)
        assert len(entry["explanation"]) > 0

    def test_sprint_drift_explanation_mentions_both_values(self):
        """Explanation states both the declared and DB-phase values directly
        — no state-machine invariant evaluation is involved for a sprint
        entry as of 030/001 (both sides are the same DB-phase vocabulary)."""
        project = FakeProject(
            [FakeSprint("001", status="planning-docs")],
            phases={"001": "ticketing"},
        )
        status = _status_dict([_sprint_entry("001", state="open")])
        result = detect_inconsistencies(project, status)
        assert len(result) == 1
        explanation = result[0]["explanation"]
        assert "planning-docs" in explanation
        assert "ticketing" in explanation
        assert "set_sprint_stage" in explanation

    def test_unrecognised_declared_sprint_status_still_reported(self):
        """A declared status that isn't a real DB-phase value is still a
        plain string mismatch — no "recognised state" check applies to
        sprints (unlike tickets, which do evaluate a state machine)."""
        project = FakeProject(
            [FakeSprint("001", status="nonexistent-phase")],
            phases={"001": "ticketing"},
        )
        status = _status_dict([_sprint_entry("001", state="open")])
        result = detect_inconsistencies(project, status)
        assert len(result) == 1
        entry = result[0]
        assert entry["kind"] == "state_drift"
        assert "nonexistent-phase" in entry["explanation"]

    def test_sprint_not_found_in_project_produces_no_entry(self):
        """If project can't find the sprint, no entry is emitted (safe default)."""
        project = FakeProject()  # no sprints registered
        status = _status_dict([_sprint_entry("999", state="open")])
        # FakeProject(999) frontmatter → None → skip
        result = detect_inconsistencies(project, status)
        assert result == []

    def test_sprint_with_no_db_record_produces_no_entry(self):
        """030/001: a sprint with a declared status but no DB registration
        has no DB-phase signal to compare against — fail-open, no entry,
        matching the existing behaviour for a missing frontmatter status."""
        project = FakeProject([FakeSprint("001", status="planning-docs")])
        # No phases= given → FakeStateDB has no record for "001".
        status = _status_dict([_sprint_entry("001", state="open")])
        result = detect_inconsistencies(project, status)
        assert result == []

    def test_multiple_sprints_only_drifting_one_flagged(self):
        """Only the sprint with a mismatch produces an entry."""
        project = FakeProject(
            [
                FakeSprint("001", status="ticketing"),      # matches
                FakeSprint("002", status="planning-docs"),  # mismatch: DB ticketing
            ],
            phases={"001": "ticketing", "002": "ticketing"},
        )
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


# ---------------------------------------------------------------------------
# Tests: terminal/archived sprints are skipped (020-009)
# ---------------------------------------------------------------------------
#
# These use a real Project/Sprint pair on tmp_path rather than
# FakeProject/FakeSprint. The behaviour under test is "does a sprint that
# was actually archived by Sprint.archive() (real frontmatter, real
# sprints/done/ layout, real machine state) get skipped" — a fake sprint
# object would let us assert whatever declared/computed pairing we like
# without ever proving the real archive path produces it. The legacy-
# `status: done` scenario in particular only exists because of how the old
# writer behaved, which is easiest to reproduce faithfully by writing the
# frontmatter directly, matching the real files under clasi/sprints/done/.


def _make_real_sprint(tmp_path, sprint_id="001", slug="test-sprint", status="planning"):
    """Create a real sprint directory (mirrors tests/unit/test_sprint.py)."""
    proj = Project(tmp_path)
    sprint_dir = proj.sprints_dir / f"{sprint_id}-{slug}"
    sprint_dir.mkdir(parents=True)
    (sprint_dir / "tickets").mkdir()
    (sprint_dir / "tickets" / "done").mkdir()
    (sprint_dir / "sprint.md").write_text(
        f"---\nid: \"{sprint_id}\"\ntitle: \"Test Sprint\"\n"
        f"status: {status}\nbranch: sprint/{sprint_id}-{slug}\n---\n"
        f"# Sprint {sprint_id}\n",
        encoding="utf-8",
    )
    return proj, sprint_dir


class TestTerminalSprintsSkipped:
    """Sprints in the machine's terminal state must not be drift-checked."""

    def test_archived_sprint_with_legacy_done_produces_no_drift(self, tmp_path):
        """A sprint archived carrying legacy frontmatter status: done must
        produce zero state_drift entries, even though 'done' is not a
        state sprint.yaml defines and therefore would mismatch whatever
        the machine computes.

        This reproduces the real defect: the 18 (now 19) sprints under
        clasi/sprints/done/ were archived by a pre-019-007 writer that
        wrote status: done directly into frontmatter. We write that same
        legacy value by hand (rather than calling Sprint.archive(), which
        now writes the correct terminal state) so the test exercises the
        actual legacy-data shape, not a shape our own fix would produce.
        """
        proj, sprint_dir = _make_real_sprint(tmp_path, status="planning")
        s = Sprint(sprint_dir, proj)
        sprint_id = s.id

        # Move to sprints/done/ and overwrite frontmatter with the legacy
        # value directly, bypassing archive()'s (now-correct) status write
        # so we faithfully reproduce the pre-019-007 archived shape.
        done_dir = proj.sprints_dir / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        new_dir = done_dir / sprint_dir.name
        sprint_dir.rename(new_dir)
        (new_dir / "sprint.md").write_text(
            f"---\nid: \"{sprint_id}\"\ntitle: \"Test Sprint\"\n"
            f"status: done\nbranch: sprint/{sprint_id}-test-sprint\n---\n"
            f"# Sprint {sprint_id}\n",
            encoding="utf-8",
        )

        from clasi.state_machine import load_machine

        terminal_state = load_machine("sprint").terminal_states()[0]

        status_dict = {
            "sprints": [
                {
                    "id": sprint_id,
                    "state": terminal_state,
                    "available_transitions": [],
                    "tickets": {"details": []},
                }
            ],
        }

        drift = [
            e
            for e in detect_inconsistencies(proj, status_dict)
            if e.get("kind") == "state_drift"
        ]
        assert drift == [], (
            f"terminal/archived sprint with legacy status produced drift: {drift}"
        )

    def test_non_terminal_sprint_with_genuine_drift_still_reports(self, tmp_path):
        """A live, non-terminal sprint whose declared status genuinely
        disagrees with its DB phase must STILL report drift.

        This is the assertion that matters most per the ticket: a skip
        that only applies to terminal/archived sprints must not silence
        drift for sprints sitting in any other (non-terminal) state.
        """
        proj, sprint_dir = _make_real_sprint(tmp_path, status="planning-docs")
        s = Sprint(sprint_dir, proj)
        sprint_id = s.id

        # Register in the DB at its default "roadmap" phase — genuinely
        # disagrees with frontmatter's "planning-docs", and the sprint is
        # neither archived nor carrying a terminal status string, so the
        # exemption must not apply.
        proj.db.register_sprint(
            sprint_id, "test-sprint", branch=f"sprint/{sprint_id}-test-sprint"
        )

        status_dict = {
            "sprints": [
                {
                    "id": sprint_id,
                    "state": "open",
                    "available_transitions": [],
                    "tickets": {"details": []},
                }
            ],
        }

        drift = [
            e
            for e in detect_inconsistencies(proj, status_dict)
            if e.get("kind") == "state_drift"
        ]
        assert len(drift) == 1, (
            f"expected genuine drift on a non-terminal sprint to still be "
            f"reported, got: {drift}"
        )
        assert drift[0]["declared"] == "planning-docs"
        assert drift[0]["computed"] == "roadmap"

    def test_stale_db_phase_behind_archived_directory_produces_no_drift(
        self, tmp_path
    ):
        """Models this repo's own live divergence (sprint 012): a sprint
        archived under sprints/done/ (frontmatter status: "done", written
        by archive()) whose DB phase was never advanced past an earlier
        value ("ticketing") — archive() intentionally does not touch DB
        phase (030/001; that remains a separate step, redesigned by
        ticket 004). The directory-location-based terminal exemption must
        still report zero drift for it, tolerating the stale DB phase
        with zero data edits — the design's own explicit acceptance
        criterion.
        """
        proj, sprint_dir = _make_real_sprint(tmp_path, status="roadmap")
        s = Sprint(sprint_dir, proj)
        sprint_id = s.id

        proj.db.register_sprint(
            sprint_id, "test-sprint", branch=f"sprint/{sprint_id}-test-sprint"
        )
        proj.db.advance_phase(sprint_id)  # roadmap -> planning-docs
        proj.db.advance_phase(sprint_id)  # planning-docs -> architecture-review
        proj.db.record_gate(sprint_id, "architecture_review", "passed")
        proj.db.advance_phase(sprint_id)  # architecture-review -> stakeholder-review
        proj.db.record_gate(sprint_id, "stakeholder_approval", "passed")
        proj.db.advance_phase(sprint_id)  # stakeholder-review -> ticketing
        # DB phase stops here at "ticketing" — mirrors sprint 012's real
        # stuck-at-"ticketing" DB row.

        s.archive()  # moves under sprints/done/, writes status: "done";
        # does NOT touch DB phase.

        assert proj.db.get_sprint_state(sprint_id)["phase"] == "ticketing"

        status_dict = {
            "sprints": [
                {
                    "id": sprint_id,
                    "state": "closed",
                    "available_transitions": [],
                    "tickets": {"details": []},
                }
            ],
        }

        drift = [
            e
            for e in detect_inconsistencies(proj, status_dict)
            if e.get("kind") == "state_drift"
        ]
        assert drift == [], (
            f"archived sprint with a stale DB phase drifted despite the "
            f"directory-based terminal exemption: {drift}"
        )

    def test_terminal_state_skip_does_not_apply_to_matching_non_terminal_state(
        self, tmp_path
    ):
        """Sanity check: a sprint whose DB phase simply is not terminal is
        never skipped by the terminal-state check — it is checked, and
        happens to match (declared == DB phase), not skipped.
        """
        proj, sprint_dir = _make_real_sprint(tmp_path, status="roadmap")
        s = Sprint(sprint_dir, proj)
        sprint_id = s.id

        # register_sprint's default phase ("roadmap") matches the
        # frontmatter this sprint was created with.
        proj.db.register_sprint(
            sprint_id, "test-sprint", branch=f"sprint/{sprint_id}-test-sprint"
        )

        status_dict = {
            "sprints": [
                {
                    "id": sprint_id,
                    "state": "open",
                    "available_transitions": [],
                    "tickets": {"details": []},
                }
            ],
        }

        # declared == DB phase == "roadmap" (non-terminal) → no drift, but
        # for the *matching* reason, not because it was skipped as
        # terminal.
        drift = [
            e
            for e in detect_inconsistencies(proj, status_dict)
            if e.get("kind") == "state_drift"
        ]
        assert drift == []


# ---------------------------------------------------------------------------
# Test: the headline 030/001 acceptance criterion
# ---------------------------------------------------------------------------


class TestHealthyActiveSprintZeroDrift:
    """A healthy active sprint, built entirely through real writers, must
    produce zero state_drift entries — not "every healthy sprint flagged",
    the pre-030 defect this ticket fixes (detect_inconsistencies used to
    compare frontmatter against a computed vocabulary disjoint from it by
    construction)."""

    def test_healthy_active_sprint_produces_zero_drift(self, tmp_path):
        proj = Project(tmp_path)
        proj.sprints_dir.mkdir(parents=True, exist_ok=True)
        proj.clasi_dir.mkdir(parents=True, exist_ok=True)
        proj.db.init()

        sprint = proj.create_sprint("Healthy Sprint")
        proj.db.register_sprint(
            sprint.id, sprint.slug, branch=f"sprint/{sprint.id}-{sprint.slug}"
        )

        # Drive several real phase transitions the way detail_sprint /
        # advance_sprint_phase do — every one routes through
        # Sprint.set_sprint_stage() as of this ticket.
        sprint.detail_promote()  # roadmap -> planning-docs
        sprint.advance_phase()  # planning-docs -> architecture-review
        sprint.record_gate("architecture_review", "passed")
        sprint.advance_phase()  # architecture-review -> stakeholder-review
        sprint.record_gate("stakeholder_approval", "passed")
        sprint.advance_phase()  # stakeholder-review -> ticketing

        assert sprint.status == "ticketing"
        assert proj.db.get_sprint_state(sprint.id)["phase"] == "ticketing"

        status_dict = {
            "sprints": [
                {
                    "id": sprint.id,
                    # The computed sprint-machine vocabulary — deliberately
                    # a different string than the DB-phase vocabulary
                    # above, and irrelevant to the sprint-level check as
                    # of 030/001 (it is no longer compared against
                    # frontmatter for drift).
                    "state": "ticketed",
                    "available_transitions": [],
                    "tickets": {"details": []},
                }
            ],
        }

        drift = [
            e
            for e in detect_inconsistencies(proj, status_dict)
            if e.get("kind") == "state_drift" and e.get("machine") == "sprint"
        ]
        assert drift == [], (
            f"a healthy active sprint, driven entirely through real "
            f"writers, must produce zero sprint-level state_drift "
            f"entries: {drift}"
        )
