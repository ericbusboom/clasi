"""Unit tests for StatusReporter and clasi.status.build_status.

All tests use a fake Project/reader so no real filesystem, git, or DB
I/O occurs.  The :class:`~clasi.state_machine.context.NullStateReader`
supplies safe defaults (all False / "" / None) so state machines
consistently reach the ``NoMatchingStateError`` path and emit
``state: "unknown"`` — which lets us verify the structural contract
without relying on any live machine configuration.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

import clasi.state_machine.predicates  # noqa: F401 — side-effect: registers all predicates
import clasi.state_machine.predicates.project
import clasi.state_machine.predicates.sprint
import clasi.state_machine.predicates.ticket
from clasi.state_machine.context import NullStateReader
from clasi.state_machine.registry import clear_registry
from clasi.status import build_status
from clasi.status.reporter import StatusReporter
from clasi.status.formatting import to_json, to_yaml


# ---------------------------------------------------------------------------
# Registry guard: re-register predicates if the registry was cleared by another
# test module's autouse fixture (e.g. test_evaluator._clean_registry).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ensure_predicates_registered():
    """Ensure all CLASI predicates are registered before each test.

    The state machine evaluator tests use ``clear_registry()`` as an autouse
    fixture to isolate registry state between their tests.  When those tests
    run before ours in the same session, the registry is left empty.  We
    restore it by reloading the predicate modules (which re-executes the
    ``@predicate(...)`` decorators) after clearing any leftover partial state.
    """
    # Clear first to avoid DuplicatePredicateError from partial registrations.
    clear_registry()
    importlib.reload(clasi.state_machine.predicates.project)
    importlib.reload(clasi.state_machine.predicates.sprint)
    importlib.reload(clasi.state_machine.predicates.ticket)
    yield


# ---------------------------------------------------------------------------
# Minimal fake objects (no I/O)
# ---------------------------------------------------------------------------


class FakeIssue:
    """Minimal stand-in for clasi.issue.Issue."""

    def __init__(self, sprint: str | None = None):
        self.sprint = sprint
        self.status = "pending"


class FakeTicket:
    """Minimal stand-in for clasi.ticket.Ticket with configurable id/status."""

    def __init__(self, ticket_id: str = "001-001"):
        self._id = ticket_id
        self.status = "open"

    @property
    def id(self) -> str:
        return self._id


class FakeSprint:
    """Minimal stand-in for clasi.sprint.Sprint."""

    def __init__(
        self,
        sprint_id: str = "001",
        tickets: list | None = None,
        status: str = "executing",
        path: "Path | None" = None,
    ):
        self._id = sprint_id
        self._tickets = tickets or []
        self.status = status
        # Real Sprint.path always resolves; None here matches every
        # pre-existing test that never sets it (the path-based terminal
        # signal in _is_terminal_sprint then fails open via its except
        # clause, same as it would for any other AttributeError).
        self.path = path

    @property
    def id(self) -> str:
        return self._id

    def list_tickets(self, status: str | None = None):
        if status is None:
            return list(self._tickets)
        return [t for t in self._tickets if t.status == status]


class FakeProject:
    """Minimal stand-in for clasi.project.Project.

    Uses keyword arguments for all injectable behaviour so individual
    tests only need to override what they care about.
    """

    def __init__(
        self,
        sprints: list | None = None,
        issues: list | None = None,
    ):
        self._sprints = sprints or []
        self._issues = issues or []

    def list_sprints(self, status: str | None = None):
        return list(self._sprints)

    def list_issues(self):
        return list(self._issues)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def null_reader():
    return NullStateReader()


@pytest.fixture()
def empty_project():
    """A project with no sprints and no issues."""
    return FakeProject()


@pytest.fixture()
def reporter_empty(empty_project, null_reader):
    return StatusReporter(empty_project, reader=null_reader)


# ---------------------------------------------------------------------------
# Top-level structure tests
# ---------------------------------------------------------------------------


class TestTopLevelKeys:
    def test_all_keys_present(self, reporter_empty):
        result = reporter_empty.build()
        expected_keys = {"agent", "computed_at", "project", "sprints", "issues", "notes", "inconsistencies"}
        assert set(result.keys()) == expected_keys

    def test_agent_default_is_team_lead(self, reporter_empty):
        result = reporter_empty.build()
        assert result["agent"] == "team-lead"

    def test_agent_custom(self, reporter_empty):
        result = reporter_empty.build(agent="programmer")
        assert result["agent"] == "programmer"

    def test_computed_at_is_string(self, reporter_empty):
        result = reporter_empty.build()
        assert isinstance(result["computed_at"], str)
        assert "T" in result["computed_at"]  # ISO-8601 contains a T separator

    def test_inconsistencies_is_empty_list(self, reporter_empty):
        result = reporter_empty.build()
        assert result["inconsistencies"] == []


# ---------------------------------------------------------------------------
# skip_inconsistencies (sprint 026 / ticket 003)
# ---------------------------------------------------------------------------


class TestSkipInconsistencies:
    """``skip_inconsistencies`` exists ONLY so the status-inject hook path
    can skip the ~400ms detect_inconsistencies pass. The default (False)
    must leave every existing caller (``clasi status`` CLI, ``get_status``
    MCP tool / project-status skill) unchanged."""

    def test_default_calls_detect_inconsistencies(self, empty_project, null_reader):
        with patch(
            "clasi.status.inconsistency.detect_inconsistencies", return_value=[]
        ) as mock_detect:
            StatusReporter(empty_project, reader=null_reader).build()
        mock_detect.assert_called_once()

    def test_skip_inconsistencies_true_does_not_call_detect(self, empty_project, null_reader):
        with patch(
            "clasi.status.inconsistency.detect_inconsistencies"
        ) as mock_detect:
            StatusReporter(empty_project, reader=null_reader).build(
                skip_inconsistencies=True
            )
        mock_detect.assert_not_called()

    def test_skip_inconsistencies_true_still_returns_empty_list(self, empty_project, null_reader):
        result = StatusReporter(empty_project, reader=null_reader).build(
            skip_inconsistencies=True
        )
        assert result["inconsistencies"] == []

    def test_skip_inconsistencies_does_not_change_other_keys(self, empty_project, null_reader):
        default_result = StatusReporter(empty_project, reader=null_reader).build()
        skipped_result = StatusReporter(empty_project, reader=null_reader).build(
            skip_inconsistencies=True
        )
        default_result.pop("computed_at")
        skipped_result.pop("computed_at")
        default_result.pop("inconsistencies")
        skipped_result.pop("inconsistencies")
        assert default_result == skipped_result

    def test_build_status_default_calls_detect_inconsistencies(self, empty_project, null_reader):
        with patch(
            "clasi.status.inconsistency.detect_inconsistencies", return_value=[]
        ) as mock_detect:
            build_status(empty_project, reader=null_reader)
        mock_detect.assert_called_once()

    def test_build_status_passes_skip_inconsistencies_through(self, empty_project, null_reader):
        with patch(
            "clasi.status.inconsistency.detect_inconsistencies"
        ) as mock_detect:
            result = build_status(
                empty_project, reader=null_reader, skip_inconsistencies=True
            )
        mock_detect.assert_not_called()
        assert result["inconsistencies"] == []


# ---------------------------------------------------------------------------
# Project block tests
# ---------------------------------------------------------------------------


class TestProjectBlock:
    def test_project_has_state_key(self, reporter_empty):
        result = reporter_empty.build()
        assert "state" in result["project"]

    def test_project_has_available_transitions_key(self, reporter_empty):
        result = reporter_empty.build()
        assert "available_transitions" in result["project"]

    def test_project_state_is_string(self, reporter_empty):
        """Project state is always a non-empty string."""
        result = reporter_empty.build()
        assert isinstance(result["project"]["state"], str)
        assert result["project"]["state"] != ""

    def test_project_state_uninitialized_with_null_reader(self, reporter_empty):
        """NullStateReader → file_exists returns False → is_overview_absent is True
        → 'uninitialized' state invariant satisfied."""
        result = reporter_empty.build()
        # NullStateReader.file_exists → False, which means the overview is
        # absent, so the `uninitialized` state matches.
        assert result["project"]["state"] == "uninitialized"

    def test_project_available_transitions_is_list(self, reporter_empty):
        result = reporter_empty.build()
        assert isinstance(result["project"]["available_transitions"], list)


# ---------------------------------------------------------------------------
# Sprints block tests
# ---------------------------------------------------------------------------


class TestSprintsBlock:
    def test_sprints_is_list(self, reporter_empty):
        result = reporter_empty.build()
        assert isinstance(result["sprints"], list)

    def test_sprints_empty_for_no_sprints(self, reporter_empty):
        result = reporter_empty.build()
        assert result["sprints"] == []

    def test_sprints_one_entry_per_sprint(self, null_reader):
        project = FakeProject(sprints=[FakeSprint("001"), FakeSprint("002")])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        assert len(result["sprints"]) == 2

    def test_sprint_entry_has_required_keys(self, null_reader):
        project = FakeProject(sprints=[FakeSprint("005")])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        sprint_entry = result["sprints"][0]
        assert "id" in sprint_entry
        assert "state" in sprint_entry
        assert "available_transitions" in sprint_entry
        assert "tickets" in sprint_entry

    def test_sprint_entry_id_matches(self, null_reader):
        project = FakeProject(sprints=[FakeSprint("007")])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        assert result["sprints"][0]["id"] == "007"

    def test_sprint_state_unknown_with_null_reader(self, null_reader):
        project = FakeProject(sprints=[FakeSprint("001")])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        assert result["sprints"][0]["state"] == "unknown"

    def test_sprint_transitions_empty_when_unknown(self, null_reader):
        project = FakeProject(sprints=[FakeSprint("001")])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        assert result["sprints"][0]["available_transitions"] == []


# ---------------------------------------------------------------------------
# Tickets sub-block tests
# ---------------------------------------------------------------------------


class TestTicketsSubBlock:
    def test_tickets_has_total_key(self, null_reader):
        project = FakeProject(sprints=[FakeSprint("001")])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        assert "total" in result["sprints"][0]["tickets"]

    def test_tickets_total_zero_for_no_tickets(self, null_reader):
        project = FakeProject(sprints=[FakeSprint("001", tickets=[])])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        assert result["sprints"][0]["tickets"]["total"] == 0

    def test_tickets_total_reflects_ticket_count(self, null_reader):
        tickets = [FakeTicket("001-01"), FakeTicket("001-02"), FakeTicket("001-03")]
        project = FakeProject(sprints=[FakeSprint("001", tickets=tickets)])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        assert result["sprints"][0]["tickets"]["total"] == 3

    def test_tickets_by_state_present_when_tickets_exist(self, null_reader):
        tickets = [FakeTicket("001-01")]
        project = FakeProject(sprints=[FakeSprint("001", tickets=tickets)])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        tickets_block = result["sprints"][0]["tickets"]
        assert "by_state" in tickets_block

    def test_tickets_details_present_when_tickets_exist(self, null_reader):
        tickets = [FakeTicket("001-01")]
        project = FakeProject(sprints=[FakeSprint("001", tickets=tickets)])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        tickets_block = result["sprints"][0]["tickets"]
        assert "details" in tickets_block

    def test_ticket_detail_has_required_keys(self, null_reader):
        tickets = [FakeTicket("001-01")]
        project = FakeProject(sprints=[FakeSprint("001", tickets=tickets)])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        detail = result["sprints"][0]["tickets"]["details"][0]
        assert "id" in detail
        assert "state" in detail
        assert "available_transitions" in detail

    def test_ticket_detail_id_matches(self, null_reader):
        tickets = [FakeTicket("042-07")]
        project = FakeProject(sprints=[FakeSprint("042", tickets=tickets)])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        assert result["sprints"][0]["tickets"]["details"][0]["id"] == "042-07"

    def test_ticket_state_unknown_with_null_reader(self, null_reader):
        tickets = [FakeTicket("001-01")]
        project = FakeProject(sprints=[FakeSprint("001", tickets=tickets)])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        assert result["sprints"][0]["tickets"]["details"][0]["state"] == "unknown"

    def test_no_by_state_or_details_when_no_tickets(self, null_reader):
        project = FakeProject(sprints=[FakeSprint("001", tickets=[])])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        tickets_block = result["sprints"][0]["tickets"]
        assert "by_state" not in tickets_block
        assert "details" not in tickets_block


# ---------------------------------------------------------------------------
# exclude_done: status-block assembly path vs. on-demand path (019-006 fix 1)
# ---------------------------------------------------------------------------


class TestExcludeDone:
    """``exclude_done`` (StatusReporter.build / _build_sprints_block /
    _build_tickets_block) must drop status: done sprints and tickets from
    the assembled dict WITHOUT changing what project.list_sprints() or
    Sprint.list_tickets() themselves return — those on-demand-query paths
    (MCP list_sprints, get_sprint_status) must keep including done/ so
    they still return full history.
    """

    def _project(self, null_reader):
        done_ticket = FakeTicket("001-01")
        done_ticket.status = "done"
        open_ticket = FakeTicket("001-02")
        open_ticket.status = "open"

        active_sprint = FakeSprint(
            "001", tickets=[done_ticket, open_ticket], status="executing"
        )
        done_sprint = FakeSprint("000", tickets=[], status="done")
        return FakeProject(sprints=[done_sprint, active_sprint])

    def test_default_excludes_nothing_same_as_list_sprints(self, null_reader):
        """Default (exclude_done=False) — same fixture, both call paths
        return identical sprint counts: the assembly path defers entirely
        to project.list_sprints(), which already includes done/."""
        project = self._project(null_reader)
        reporter = StatusReporter(project, reader=null_reader)

        result = reporter.build()
        direct = project.list_sprints()

        assert len(result["sprints"]) == len(direct) == 2
        ids = {s["id"] for s in result["sprints"]}
        assert ids == {"000", "001"}

    def test_exclude_done_removes_done_sprint(self, null_reader):
        project = self._project(null_reader)
        reporter = StatusReporter(project, reader=null_reader)

        result = reporter.build(exclude_done=True)

        ids = {s["id"] for s in result["sprints"]}
        assert ids == {"001"}

    def test_exclude_done_removes_done_tickets_from_remaining_sprint(self, null_reader):
        project = self._project(null_reader)
        reporter = StatusReporter(project, reader=null_reader)

        result = reporter.build(exclude_done=True)

        sprint_001 = next(s for s in result["sprints"] if s["id"] == "001")
        detail_ids = {d["id"] for d in sprint_001["tickets"]["details"]}
        assert detail_ids == {"001-02"}
        assert sprint_001["tickets"]["total"] == 1

    def test_exclude_done_does_not_mutate_list_sprints_or_list_tickets(self, null_reader):
        """The same fixture, queried directly via list_sprints()/
        list_tickets(), must be unaffected by exclude_done=True having
        been used on the status-block build path — proves the two paths
        differ only in the done/ exclusion, not in underlying behavior."""
        project = self._project(null_reader)
        reporter = StatusReporter(project, reader=null_reader)

        # Exercise the exclude_done path first.
        reporter.build(exclude_done=True)

        # Direct on-demand queries still see everything, including done/.
        direct_sprints = project.list_sprints()
        assert len(direct_sprints) == 2
        assert {s.id for s in direct_sprints} == {"000", "001"}

        active_sprint = next(s for s in direct_sprints if s.id == "001")
        direct_tickets = active_sprint.list_tickets()
        assert len(direct_tickets) == 2
        assert {t.id for t in direct_tickets} == {"001-01", "001-02"}

    def test_exclude_done_false_keeps_done_ticket_details(self, null_reader):
        project = self._project(null_reader)
        reporter = StatusReporter(project, reader=null_reader)

        result = reporter.build(exclude_done=False)

        sprint_001 = next(s for s in result["sprints"] if s["id"] == "001")
        detail_ids = {d["id"] for d in sprint_001["tickets"]["details"]}
        assert detail_ids == {"001-01", "001-02"}


# ---------------------------------------------------------------------------
# exclude_done widened to terminal ("closed") status and done/-path archived
# sprints (026/007) — ticket 003 measured that the six archived sprints in
# this repo declare status: closed (the sprint machine's own terminal state
# name), which is NOT "done" (the ticket machine's terminal state name), so
# they leaked past the original exclude_done check.
# ---------------------------------------------------------------------------


class TestExcludeDoneWidenedToClosedArchived:
    def test_exclude_done_removes_closed_status_sprint(self, null_reader):
        """A sprint declaring status: closed (no done/ path signal) must be
        excluded by exclude_done the same way status: done already is —
        this is the exact real-repo mismatch ticket 003 measured."""
        active = FakeSprint("026", tickets=[], status="executing")
        closed = FakeSprint("020", tickets=[], status="closed")
        project = FakeProject(sprints=[closed, active])
        reporter = StatusReporter(project, reader=null_reader)

        result = reporter.build(exclude_done=True)

        ids = {s["id"] for s in result["sprints"]}
        assert ids == {"026"}

    def test_exclude_done_false_keeps_closed_sprint(self, null_reader):
        """On-demand callers (exclude_done=False, e.g. clasi status CLI)
        must be completely unaffected by the widened terminal check —
        closed/archived sprints still appear, unchanged."""
        active = FakeSprint("026", tickets=[], status="executing")
        closed = FakeSprint("020", tickets=[], status="closed")
        project = FakeProject(sprints=[closed, active])
        reporter = StatusReporter(project, reader=null_reader)

        result = reporter.build(exclude_done=False)

        ids = {s["id"] for s in result["sprints"]}
        assert ids == {"020", "026"}

    def test_exclude_done_removes_sprint_under_done_dir_regardless_of_status(
        self, null_reader
    ):
        """A sprint physically located under sprints/done/ must be excluded
        by directory location alone, even if its declared status: is
        neither 'done' nor 'closed' (stale/missing/future terminal label) —
        the ticket's acceptance criteria requires not relying on
        frontmatter alone when the directory already signals archived."""
        active = FakeSprint(
            "026",
            tickets=[],
            status="executing",
            path=Path("/fake/project/clasi/sprints/026-active"),
        )
        archived_by_path_only = FakeSprint(
            "011",
            tickets=[],
            status="some-future-terminal-label",
            path=Path("/fake/project/clasi/sprints/done/011-archived"),
        )
        project = FakeProject(sprints=[archived_by_path_only, active])
        reporter = StatusReporter(project, reader=null_reader)

        result = reporter.build(exclude_done=True)

        ids = {s["id"] for s in result["sprints"]}
        assert ids == {"026"}

    def test_exclude_done_still_removes_done_status_sprint_unchanged(
        self, null_reader
    ):
        """Regression: the original status: done exclusion (pre-026/007)
        must not have been narrowed by widening to also match closed/path —
        both signals are additive, not a replacement."""
        active = FakeSprint("026", tickets=[], status="executing")
        done = FakeSprint("001", tickets=[], status="done")
        project = FakeProject(sprints=[done, active])
        reporter = StatusReporter(project, reader=null_reader)

        result = reporter.build(exclude_done=True)

        ids = {s["id"] for s in result["sprints"]}
        assert ids == {"026"}


# ---------------------------------------------------------------------------
# Transition entry tests
# ---------------------------------------------------------------------------


class TestTransitionEntries:
    """Transitions only appear when a state IS matched (non-null reader).

    With NullStateReader no state matches so transitions are always [].
    We test the shape by checking the project block uses the right dict keys
    when we supply a custom reader that makes a state match.
    """

    def test_transition_entry_keys_when_state_matches(self):
        """NullStateReader → is_overview_absent = True → uninitialized state matches.
        The uninitialized state has one outbound transition: `initialize`."""
        project = FakeProject()
        reporter = StatusReporter(project, reader=NullStateReader())
        result = reporter.build()
        # uninitialized state has one transition: `initialize`
        transitions = result["project"]["available_transitions"]
        assert len(transitions) == 1
        t = transitions[0]
        assert "name" in t
        assert "to" in t
        assert "fireable" in t
        assert "blocked_by" in t
        assert isinstance(t["blocked_by"], list)

    def test_transition_fireable_is_bool(self):
        project = FakeProject()
        reporter = StatusReporter(project, reader=NullStateReader())
        result = reporter.build()
        for t in result["project"]["available_transitions"]:
            assert isinstance(t["fireable"], bool)


# ---------------------------------------------------------------------------
# Issues block tests
# ---------------------------------------------------------------------------


class TestIssuesBlock:
    def test_issues_has_required_keys(self, reporter_empty):
        result = reporter_empty.build()
        issues = result["issues"]
        assert "total" in issues
        assert "pending" in issues
        assert "assigned_to_sprint" in issues

    def test_issues_zeros_for_no_issues(self, reporter_empty):
        result = reporter_empty.build()
        issues = result["issues"]
        assert issues["total"] == 0
        assert issues["pending"] == 0
        assert issues["assigned_to_sprint"] == 0

    def test_issues_counts_pending(self, null_reader):
        project = FakeProject(issues=[FakeIssue(), FakeIssue(), FakeIssue()])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        assert result["issues"]["total"] == 3
        assert result["issues"]["pending"] == 3
        assert result["issues"]["assigned_to_sprint"] == 0

    def test_issues_counts_assigned(self, null_reader):
        project = FakeProject(issues=[
            FakeIssue(sprint="001"),
            FakeIssue(sprint="002"),
            FakeIssue(),
        ])
        reporter = StatusReporter(project, reader=null_reader)
        result = reporter.build()
        assert result["issues"]["total"] == 3
        assert result["issues"]["pending"] == 1
        assert result["issues"]["assigned_to_sprint"] == 2


# ---------------------------------------------------------------------------
# Notes block tests
# ---------------------------------------------------------------------------


class TestNotesBlock:
    def test_notes_has_required_keys(self, reporter_empty):
        result = reporter_empty.build()
        notes = result["notes"]
        assert "current_focus" in notes
        assert "allowed_next_actions" in notes
        assert "blocked_actions" in notes

    def test_notes_current_focus_is_string(self, reporter_empty):
        result = reporter_empty.build()
        assert isinstance(result["notes"]["current_focus"], str)

    def test_notes_allowed_next_actions_is_list(self, reporter_empty):
        result = reporter_empty.build()
        assert isinstance(result["notes"]["allowed_next_actions"], list)

    def test_notes_blocked_actions_is_list(self, reporter_empty):
        result = reporter_empty.build()
        assert isinstance(result["notes"]["blocked_actions"], list)

    def test_notes_focus_mentions_project_state(self, reporter_empty):
        """With an empty project (no in-progress tickets, no executing sprints),
        focus falls back to describing the project state."""
        result = reporter_empty.build()
        focus = result["notes"]["current_focus"]
        # Focus must be a non-empty descriptive string
        assert isinstance(focus, str)
        assert len(focus) > 0


# ---------------------------------------------------------------------------
# build_status public entry point
# ---------------------------------------------------------------------------


class TestBuildStatus:
    def test_build_status_returns_dict(self, empty_project, null_reader):
        result = build_status(empty_project, reader=null_reader)
        assert isinstance(result, dict)

    def test_build_status_passes_agent(self, empty_project, null_reader):
        result = build_status(empty_project, agent="sprint-planner", reader=null_reader)
        assert result["agent"] == "sprint-planner"

    def test_build_status_default_agent(self, empty_project, null_reader):
        result = build_status(empty_project, reader=null_reader)
        assert result["agent"] == "team-lead"

    def test_build_status_has_all_keys(self, empty_project, null_reader):
        result = build_status(empty_project, reader=null_reader)
        assert "agent" in result
        assert "computed_at" in result
        assert "project" in result
        assert "sprints" in result
        assert "issues" in result
        assert "notes" in result
        assert "inconsistencies" in result


# ---------------------------------------------------------------------------
# Formatting helper tests
# ---------------------------------------------------------------------------


class TestFormatting:
    def test_to_yaml_is_parseable(self, reporter_empty):
        result = reporter_empty.build()
        yaml_str = to_yaml(result)
        parsed = yaml.safe_load(yaml_str)
        assert isinstance(parsed, dict)
        assert "agent" in parsed

    def test_to_json_is_parseable(self, reporter_empty):
        result = reporter_empty.build()
        json_str = to_json(result)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert "agent" in parsed

    def test_to_yaml_preserves_structure(self, reporter_empty):
        result = reporter_empty.build()
        yaml_str = to_yaml(result)
        parsed = yaml.safe_load(yaml_str)
        assert set(parsed.keys()) == set(result.keys())

    def test_to_json_preserves_structure(self, reporter_empty):
        result = reporter_empty.build()
        json_str = to_json(result)
        parsed = json.loads(json_str)
        assert set(parsed.keys()) == set(result.keys())
