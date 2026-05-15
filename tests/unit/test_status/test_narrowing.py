"""Unit tests for clasi.status.narrowing.narrow_status.

All tests use a minimal hand-built full-status dict — no I/O, no real
project objects.  The dict shape mirrors the output of StatusReporter so
the narrowing logic can be tested in complete isolation.
"""

from __future__ import annotations

import copy

import pytest

from clasi.status.narrowing import narrow_status


# ---------------------------------------------------------------------------
# Fixtures: minimal full-status dicts
# ---------------------------------------------------------------------------


def _make_ticket(ticket_id: str, state: str = "open") -> dict:
    return {
        "id": ticket_id,
        "state": state,
        "available_transitions": [
            {"name": "finish", "to": "done", "fireable": False, "blocked_by": ["is_tests_passing"]},
        ],
    }


def _make_sprint(
    sprint_id: str,
    state: str = "executing",
    tickets: list[dict] | None = None,
    with_details: bool = True,
) -> dict:
    tix = tickets or []
    tickets_block: dict = {"total": len(tix)}
    if tix:
        by_state: dict[str, int] = {}
        for t in tix:
            s = t.get("state", "open")
            by_state[s] = by_state.get(s, 0) + 1
        tickets_block["by_state"] = by_state
        if with_details:
            tickets_block["details"] = tix
    return {
        "id": sprint_id,
        "state": state,
        "available_transitions": [
            {"name": "complete", "to": "done", "fireable": False, "blocked_by": ["is_all_tickets_done"]},
        ],
        "tickets": tickets_block,
    }


@pytest.fixture()
def full_status() -> dict:
    """A minimal full-status dict with two sprints and two tickets."""
    return {
        "agent": "team-lead",
        "computed_at": "2026-01-01T00:00:00+00:00",
        "project": {
            "state": "in-sprint",
            "available_transitions": [
                {"name": "finalize", "to": "done", "fireable": True, "blocked_by": []},
            ],
        },
        "sprints": [
            _make_sprint(
                "022",
                state="executing",
                tickets=[
                    _make_ticket("022-01", "done"),
                    _make_ticket("022-03", "in-progress"),
                ],
            ),
            _make_sprint(
                "023",
                state="planned",
                tickets=[
                    _make_ticket("023-01", "open"),
                ],
            ),
        ],
        "issues": {"total": 3, "pending": 2, "assigned_to_sprint": 1},
        "notes": {
            "current_focus": "Ticket 022-03 is in-progress in sprint 022",
            "allowed_next_actions": ["Fire `finalize` on project"],
            "blocked_actions": [
                "Fire `complete` on sprint 022 — blocked by is_all_tickets_done"
            ],
        },
        "inconsistencies": [],
    }


# ---------------------------------------------------------------------------
# team-lead: returns full dict unchanged
# ---------------------------------------------------------------------------


class TestTeamLead:
    def test_returns_full_unchanged(self, full_status):
        result = narrow_status(full_status, "team-lead")
        assert result == full_status

    def test_does_not_mutate_input(self, full_status):
        original = copy.deepcopy(full_status)
        narrow_status(full_status, "team-lead")
        assert full_status == original

    def test_agent_field_is_team_lead(self, full_status):
        result = narrow_status(full_status, "team-lead")
        assert result["agent"] == "team-lead"

    def test_returns_deep_copy(self, full_status):
        result = narrow_status(full_status, "team-lead")
        # Modifying the result must not affect the original
        result["sprints"].clear()
        assert len(full_status["sprints"]) == 2


# ---------------------------------------------------------------------------
# sprint-planner WITH sprint_id
# ---------------------------------------------------------------------------


class TestSprintPlannerWithId:
    def test_project_block_unchanged(self, full_status):
        result = narrow_status(full_status, "sprint-planner", sprint_id="022")
        assert result["project"] == full_status["project"]

    def test_only_matching_sprint_present(self, full_status):
        result = narrow_status(full_status, "sprint-planner", sprint_id="022")
        assert len(result["sprints"]) == 1
        assert result["sprints"][0]["id"] == "022"

    def test_other_sprint_removed(self, full_status):
        result = narrow_status(full_status, "sprint-planner", sprint_id="022")
        ids = [s["id"] for s in result["sprints"]]
        assert "023" not in ids

    def test_tickets_has_total_and_by_state(self, full_status):
        result = narrow_status(full_status, "sprint-planner", sprint_id="022")
        tickets = result["sprints"][0]["tickets"]
        assert "total" in tickets
        assert "by_state" in tickets

    def test_tickets_no_details(self, full_status):
        result = narrow_status(full_status, "sprint-planner", sprint_id="022")
        tickets = result["sprints"][0]["tickets"]
        assert "details" not in tickets

    def test_notes_recomputed(self, full_status):
        result = narrow_status(full_status, "sprint-planner", sprint_id="022")
        notes = result["notes"]
        assert "current_focus" in notes
        assert "allowed_next_actions" in notes
        assert "blocked_actions" in notes

    def test_notes_no_fallback(self, full_status):
        result = narrow_status(full_status, "sprint-planner", sprint_id="022")
        assert "fallback" not in result["notes"]

    def test_notes_scoped_to_sprint(self, full_status):
        """Blocked actions must reference only sprint 022, not 023."""
        result = narrow_status(full_status, "sprint-planner", sprint_id="022")
        blocked = result["notes"]["blocked_actions"]
        for action in blocked:
            assert "023" not in action

    def test_nonexistent_sprint_produces_empty_sprints(self, full_status):
        result = narrow_status(full_status, "sprint-planner", sprint_id="999")
        assert result["sprints"] == []

    def test_agent_field_is_sprint_planner(self, full_status):
        result = narrow_status(full_status, "sprint-planner", sprint_id="022")
        assert result["agent"] == "sprint-planner"

    def test_does_not_mutate_input(self, full_status):
        original = copy.deepcopy(full_status)
        narrow_status(full_status, "sprint-planner", sprint_id="022")
        assert full_status == original


# ---------------------------------------------------------------------------
# sprint-planner WITHOUT sprint_id (fallback)
# ---------------------------------------------------------------------------


class TestSprintPlannerFallback:
    def test_all_sprints_present(self, full_status):
        result = narrow_status(full_status, "sprint-planner")
        assert len(result["sprints"]) == 2

    def test_no_details_in_any_sprint(self, full_status):
        result = narrow_status(full_status, "sprint-planner")
        for sprint_entry in result["sprints"]:
            assert "details" not in sprint_entry["tickets"]

    def test_fallback_note_present(self, full_status):
        result = narrow_status(full_status, "sprint-planner")
        assert "fallback" in result["notes"]

    def test_fallback_note_is_string(self, full_status):
        result = narrow_status(full_status, "sprint-planner")
        assert isinstance(result["notes"]["fallback"], str)
        assert len(result["notes"]["fallback"]) > 0

    def test_notes_has_standard_keys(self, full_status):
        result = narrow_status(full_status, "sprint-planner")
        notes = result["notes"]
        assert "current_focus" in notes
        assert "allowed_next_actions" in notes
        assert "blocked_actions" in notes

    def test_agent_field_is_sprint_planner(self, full_status):
        result = narrow_status(full_status, "sprint-planner")
        assert result["agent"] == "sprint-planner"


# ---------------------------------------------------------------------------
# programmer WITH ticket_id
# ---------------------------------------------------------------------------


class TestProgrammerWithTicketId:
    def test_project_block_present(self, full_status):
        result = narrow_status(full_status, "programmer", ticket_id="022-03")
        assert "project" in result

    def test_project_block_unchanged(self, full_status):
        result = narrow_status(full_status, "programmer", ticket_id="022-03")
        assert result["project"] == full_status["project"]

    def test_sprints_contains_only_parent_sprint(self, full_status):
        result = narrow_status(full_status, "programmer", ticket_id="022-03")
        assert len(result["sprints"]) == 1
        assert result["sprints"][0]["id"] == "022"

    def test_parent_sprint_summary_has_id_and_state(self, full_status):
        result = narrow_status(full_status, "programmer", ticket_id="022-03")
        sprint = result["sprints"][0]
        assert "id" in sprint
        assert "state" in sprint

    def test_parent_sprint_summary_no_available_transitions(self, full_status):
        """Programmer view of sprint should be summary only (id + state)."""
        result = narrow_status(full_status, "programmer", ticket_id="022-03")
        sprint = result["sprints"][0]
        assert "available_transitions" not in sprint

    def test_ticket_details_contains_only_target_ticket(self, full_status):
        result = narrow_status(full_status, "programmer", ticket_id="022-03")
        details = result["sprints"][0]["tickets"]["details"]
        assert len(details) == 1
        assert details[0]["id"] == "022-03"

    def test_notes_focuses_on_ticket(self, full_status):
        result = narrow_status(full_status, "programmer", ticket_id="022-03")
        focus = result["notes"]["current_focus"]
        assert "022-03" in focus

    def test_notes_has_standard_keys(self, full_status):
        result = narrow_status(full_status, "programmer", ticket_id="022-03")
        notes = result["notes"]
        assert "current_focus" in notes
        assert "allowed_next_actions" in notes
        assert "blocked_actions" in notes

    def test_notes_no_fallback(self, full_status):
        result = narrow_status(full_status, "programmer", ticket_id="022-03")
        assert "fallback" not in result["notes"]

    def test_agent_field_is_programmer(self, full_status):
        result = narrow_status(full_status, "programmer", ticket_id="022-03")
        assert result["agent"] == "programmer"

    def test_does_not_mutate_input(self, full_status):
        original = copy.deepcopy(full_status)
        narrow_status(full_status, "programmer", ticket_id="022-03")
        assert full_status == original

    def test_sprint_id_inferred_from_ticket_id(self, full_status):
        """Sprint id is inferred from the ticket id prefix."""
        result = narrow_status(full_status, "programmer", ticket_id="022-03")
        assert result["sprints"][0]["id"] == "022"

    def test_nonexistent_ticket_produces_empty_sprints(self, full_status):
        result = narrow_status(full_status, "programmer", ticket_id="099-01")
        assert result["sprints"] == []


# ---------------------------------------------------------------------------
# programmer WITHOUT ticket_id (fallback)
# ---------------------------------------------------------------------------


class TestProgrammerFallback:
    def test_fallback_note_present(self, full_status):
        result = narrow_status(full_status, "programmer")
        assert "fallback" in result["notes"]

    def test_fallback_note_is_string(self, full_status):
        result = narrow_status(full_status, "programmer")
        assert isinstance(result["notes"]["fallback"], str)
        assert len(result["notes"]["fallback"]) > 0

    def test_agent_field_is_programmer(self, full_status):
        result = narrow_status(full_status, "programmer")
        assert result["agent"] == "programmer"

    def test_falls_back_to_sprint_planner_view_with_sprint_id(self, full_status):
        """When ticket_id is absent but sprint_id is given, behaves like sprint-planner."""
        result = narrow_status(full_status, "programmer", sprint_id="022")
        # Only the matching sprint should appear
        assert len(result["sprints"]) == 1
        assert result["sprints"][0]["id"] == "022"
        # No ticket details
        assert "details" not in result["sprints"][0]["tickets"]

    def test_falls_back_to_team_lead_view_without_sprint_id(self, full_status):
        """When neither ticket_id nor sprint_id is given, all sprints appear."""
        result = narrow_status(full_status, "programmer")
        assert len(result["sprints"]) == 2

    def test_no_ticket_details_in_fallback(self, full_status):
        result = narrow_status(full_status, "programmer")
        for sprint_entry in result["sprints"]:
            assert "details" not in sprint_entry.get("tickets", {})

    def test_notes_has_standard_keys(self, full_status):
        result = narrow_status(full_status, "programmer")
        notes = result["notes"]
        assert "current_focus" in notes
        assert "allowed_next_actions" in notes
        assert "blocked_actions" in notes


# ---------------------------------------------------------------------------
# Public API: clasi.status.narrow_status (re-export)
# ---------------------------------------------------------------------------


class TestPublicApiExport:
    def test_narrow_status_importable_from_package(self):
        from clasi.status import narrow_status as ns
        assert callable(ns)

    def test_narrow_status_team_lead_passthrough(self, full_status):
        from clasi.status import narrow_status as ns
        result = ns(full_status, "team-lead")
        assert result == full_status
