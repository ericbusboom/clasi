"""StatusReporter — assembles the full CLASI status dict.

:class:`StatusReporter` evaluates the project, sprint, and ticket state
machines against real (or injected) state data and returns the nested dict
whose shape is documented in the issue
`clasi-status-per-agent-process-status-with-gate-derived-next-step-notes.md`.

The dict is suitable for direct YAML/JSON serialization via
:mod:`clasi.status.formatting`.

Output shape (team-lead view)::

    agent: team-lead
    computed_at: "2026-01-01T00:00:00"
    project:
      state: planning
      available_transitions:
        - name: enter-sprint
          to: in-sprint
          fireable: false
          blocked_by:
            - is_any_sprint_ticketed
    sprints:
      - id: "001"
        state: planned
        available_transitions: [...]
        tickets:
          total: 0
    issues:
      total: 7
      pending: 5
      assigned_to_sprint: 2
    notes:
      current_focus: "..."
      allowed_next_actions: [...]
      blocked_actions: [...]
    inconsistencies: []
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from clasi.state_machine import (
    NoMatchingStateError,
    ProjectContext,
    SprintContext,
    TicketContext,
    evaluate_state,
    inspect_transitions,
    load_machine,
)

if TYPE_CHECKING:
    from clasi.project import Project
    from clasi.state_machine.context import StateReader


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


class StatusReporter:
    """Assemble the full status dict from state machine evaluations.

    Args:
        project: The CLASI project whose state is being reported.
        reader: A :class:`~clasi.state_machine.context.StateReader`
            implementation used to answer predicate questions.  Defaults to
            :class:`~clasi.status.reader.ClasiStateReader` if not provided.
    """

    def __init__(self, project: "Project", reader: "StateReader | None" = None) -> None:
        self._project = project
        if reader is None:
            from clasi.status.reader import ClasiStateReader
            reader = ClasiStateReader(project)
        self._reader = reader

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        agent: str = "team-lead",
        sprint_id: str | None = None,
        ticket_id: str | None = None,
    ) -> dict:
        """Build and return the full status dict.

        Evaluates the project machine, each existing sprint machine, and
        (for executing sprints) each ticket machine. Assembles the nested
        dict matching the canonical output shape.

        The ``inconsistencies:`` key is always an empty list; population is
        deferred to ticket 004.

        Args:
            agent: The requesting agent name (e.g. ``"team-lead"``,
                ``"sprint-planner"``, ``"programmer"``).  Stored verbatim
                in the output; scope narrowing is ticket 003's job.
            sprint_id: Optional sprint ID hint (stored for callers; not
                used for narrowing here).
            ticket_id: Optional ticket ID hint (stored for callers; not
                used for narrowing here).

        Returns:
            A dict with top-level keys: ``agent``, ``computed_at``,
            ``project``, ``sprints``, ``issues``, ``notes``,
            ``inconsistencies``.
        """
        reader = self._reader
        project = self._project

        # --- project block ---
        project_block = self._build_project_block(reader)

        # --- sprints block ---
        sprints_block = self._build_sprints_block(reader, project)

        # --- issues block ---
        issues_block = self._build_issues_block(project)

        # --- notes block ---
        notes_block = self._build_notes_block(project_block, sprints_block)

        # --- assemble ---
        status: dict = {
            "agent": agent,
            "computed_at": datetime.now(tz=timezone.utc).isoformat(),
            "project": project_block,
            "sprints": sprints_block,
            "issues": issues_block,
            "notes": notes_block,
            "inconsistencies": [],  # ticket 004 fills this in
        }

        return status

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _transition_results_to_dicts(self, results: list) -> list[dict]:
        """Convert a list of TransitionResult objects to plain dicts."""
        out = []
        for tr in results:
            out.append({
                "name": tr.name,
                "to": tr.to,
                "fireable": tr.fireable,
                "blocked_by": list(tr.blocked_by),
            })
        return out

    def _build_project_block(self, reader: "StateReader") -> dict:
        """Evaluate the project state machine and return the project block."""
        machine = load_machine("project")
        ctx = ProjectContext(reader=reader)
        try:
            state = evaluate_state(machine, ctx)
            state_name = state.name
            transitions = self._transition_results_to_dicts(
                inspect_transitions(machine, state_name, ctx)
            )
        except NoMatchingStateError:
            state_name = "unknown"
            transitions = []
        return {
            "state": state_name,
            "available_transitions": transitions,
        }

    def _build_sprint_block(
        self,
        sprint,  # clasi.sprint.Sprint
        reader: "StateReader",
    ) -> dict:
        """Evaluate a single sprint's state machine and return the sprint block."""
        sprint_id = sprint.id
        machine = load_machine("sprint")
        project_ctx = ProjectContext(reader=reader)
        sprint_ctx = SprintContext(
            sprint_id=sprint_id, reader=reader, project=project_ctx
        )

        try:
            state = evaluate_state(machine, sprint_ctx)
            state_name = state.name
            transitions = self._transition_results_to_dicts(
                inspect_transitions(machine, state_name, sprint_ctx)
            )
        except NoMatchingStateError:
            state_name = "unknown"
            transitions = []

        # --- tickets sub-block ---
        tickets_block = self._build_tickets_block(sprint, reader, sprint_ctx, state_name)

        return {
            "id": sprint_id,
            "state": state_name,
            "available_transitions": transitions,
            "tickets": tickets_block,
        }

    def _build_tickets_block(
        self,
        sprint,
        reader: "StateReader",
        sprint_ctx: "SprintContext",
        sprint_state: str,
    ) -> dict:
        """Build the tickets sub-block for a sprint entry.

        Iterates every ticket in the sprint (active + done directories).
        Evaluates the ticket machine for each and assembles per-ticket detail
        entries.
        """
        try:
            all_tickets = sprint.list_tickets()
        except Exception:
            all_tickets = []

        total = len(all_tickets)
        by_state: dict[str, int] = {}
        details: list[dict] = []

        machine = load_machine("ticket")

        for ticket in all_tickets:
            ticket_id = ticket.id
            ticket_ctx = TicketContext(
                ticket_id=ticket_id,
                sprint_id=sprint.id,
                reader=reader,
                sprint=sprint_ctx,
            )

            try:
                t_state = evaluate_state(machine, ticket_ctx)
                t_state_name = t_state.name
                t_transitions = self._transition_results_to_dicts(
                    inspect_transitions(machine, t_state_name, ticket_ctx)
                )
            except NoMatchingStateError:
                t_state_name = "unknown"
                t_transitions = []

            by_state[t_state_name] = by_state.get(t_state_name, 0) + 1
            details.append({
                "id": ticket_id,
                "state": t_state_name,
                "available_transitions": t_transitions,
            })

        block: dict = {"total": total}
        if total > 0:
            block["by_state"] = by_state
            block["details"] = details

        return block

    def _build_sprints_block(
        self, reader: "StateReader", project: "Project"
    ) -> list[dict]:
        """Iterate all sprints and build the sprints list."""
        try:
            sprints = project.list_sprints()
        except Exception:
            return []
        return [self._build_sprint_block(s, reader) for s in sprints]

    def _build_issues_block(self, project: "Project") -> dict:
        """Count all pending-pool issues and return the issues block."""
        try:
            issues = project.list_issues()
        except Exception:
            issues = []

        total = len(issues)
        pending = 0
        assigned = 0
        for issue in issues:
            try:
                if issue.sprint:
                    assigned += 1
                else:
                    pending += 1
            except Exception:
                pending += 1

        return {
            "total": total,
            "pending": pending,
            "assigned_to_sprint": assigned,
        }

    def _build_notes_block(
        self, project_block: dict, sprints_block: list[dict]
    ) -> dict:
        """Derive a notes block from the assembled project and sprint state.

        ``current_focus`` is a brief human-readable sentence about the most
        actionable item visible.  ``allowed_next_actions`` lists transitions
        that are currently fireable.  ``blocked_actions`` lists transitions
        that are not fireable with the name of the first blocking predicate.

        This is a best-effort derivation; it is intentionally heuristic.
        """
        allowed: list[str] = []
        blocked: list[str] = []

        # Collect from project transitions
        for t in project_block.get("available_transitions", []):
            if t.get("fireable"):
                allowed.append(f"Fire `{t['name']}` on project")
            else:
                blockers = t.get("blocked_by", [])
                blocker_str = ", ".join(blockers) if blockers else "unknown"
                blocked.append(
                    f"Fire `{t['name']}` on project — blocked by {blocker_str}"
                )

        # Collect from sprints
        for sprint_entry in sprints_block:
            sid = sprint_entry.get("id", "")
            for t in sprint_entry.get("available_transitions", []):
                if t.get("fireable"):
                    allowed.append(f"Fire `{t['name']}` on sprint {sid}")
                else:
                    blockers = t.get("blocked_by", [])
                    blocker_str = ", ".join(blockers) if blockers else "unknown"
                    blocked.append(
                        f"Fire `{t['name']}` on sprint {sid} — blocked by {blocker_str}"
                    )

            # Collect from ticket details
            tickets = sprint_entry.get("tickets", {})
            for ticket_entry in tickets.get("details", []):
                tid = ticket_entry.get("id", "")
                t_state = ticket_entry.get("state", "")
                for t in ticket_entry.get("available_transitions", []):
                    if t.get("fireable"):
                        allowed.append(
                            f"Fire `{t['name']}` on ticket {tid}"
                        )
                    else:
                        blockers = t.get("blocked_by", [])
                        blocker_str = ", ".join(blockers) if blockers else "unknown"
                        blocked.append(
                            f"Fire `{t['name']}` on ticket {tid} — blocked by {blocker_str}"
                        )

        # Derive current_focus from first in-progress ticket, or project state
        focus = _derive_focus(project_block, sprints_block)

        return {
            "current_focus": focus,
            "allowed_next_actions": allowed,
            "blocked_actions": blocked,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _derive_focus(project_block: dict, sprints_block: list[dict]) -> str:
    """Return a short sentence describing the most actionable current item."""
    # Look for any in-progress ticket first
    for sprint_entry in sprints_block:
        sid = sprint_entry.get("id", "")
        tickets = sprint_entry.get("tickets", {})
        for ticket_entry in tickets.get("details", []):
            if ticket_entry.get("state") == "in-progress":
                tid = ticket_entry.get("id", "")
                return f"Ticket {tid} is in-progress in sprint {sid}"

    # Then executing sprints
    for sprint_entry in sprints_block:
        if sprint_entry.get("state") == "executing":
            sid = sprint_entry.get("id", "")
            return f"Sprint {sid} is executing"

    # Fall back to project state
    p_state = project_block.get("state", "unknown")
    return f"Project is in state: {p_state}"
