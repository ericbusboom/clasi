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
        exclude_done: bool = False,
        skip_inconsistencies: bool = False,
    ) -> dict:
        """Build and return the full status dict.

        Evaluates the project machine, each existing sprint machine, and
        (for executing sprints) each ticket machine. Assembles the nested
        dict matching the canonical output shape.

        The ``inconsistencies:`` key is populated by
        :func:`~clasi.status.inconsistency.detect_inconsistencies`, unless
        *skip_inconsistencies* is True (see below).

        Args:
            agent: The requesting agent name (e.g. ``"team-lead"``,
                ``"sprint-planner"``, ``"programmer"``).  Stored verbatim
                in the output; scope narrowing is ticket 003's job.
            sprint_id: Optional sprint ID hint (stored for callers; not
                used for narrowing here).
            ticket_id: Optional ticket ID hint (stored for callers; not
                used for narrowing here).
            exclude_done: When True, terminal (archived) sprints — see
                :func:`_is_terminal_sprint` — and tickets with
                ``status: done`` are excluded from the assembled dict.
                Intended ONLY for the per-prompt status-block hook path
                (``hook_handlers._build_status_block``), which must stay
                small. On-demand callers (MCP ``list_sprints``,
                ``get_sprint_status``, the ``status`` CLI/MCP tool) must
                keep the default ``False`` so they continue to return full
                history including archived (``done/``) sprints and
                tickets.
            skip_inconsistencies: When True, ``detect_inconsistencies`` is
                not run and ``inconsistencies`` is returned as ``[]``.
                Intended ONLY for the ``status-inject`` (``UserPromptSubmit``)
                hook path — sprint 026 measured this pass at about 400ms
                running inline on every prompt for no per-prompt benefit.
                The ``clasi status`` CLI and the ``project-status`` skill
                (via MCP ``get_status``) must keep the default ``False``
                so drift detection stays available on demand, unchanged.

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
        sprints_block = self._build_sprints_block(
            reader, project, exclude_done=exclude_done
        )

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
            "inconsistencies": [],
        }

        # --- inconsistency detection ---
        if not skip_inconsistencies:
            from clasi.status.inconsistency import detect_inconsistencies
            status["inconsistencies"] = detect_inconsistencies(project, status)

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
        exclude_done: bool = False,
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
        tickets_block = self._build_tickets_block(
            sprint, reader, sprint_ctx, state_name, exclude_done=exclude_done
        )

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
        exclude_done: bool = False,
    ) -> dict:
        """Build the tickets sub-block for a sprint entry.

        Iterates every ticket in the sprint (active + done directories).
        Evaluates the ticket machine for each and assembles per-ticket detail
        entries.

        When *exclude_done* is True, tickets with ``status: done`` in their
        frontmatter are omitted. This is used ONLY by the status-block hook
        path to keep the per-prompt injection small — on-demand callers
        (MCP tools) always pass the default ``False`` and see full history.
        """
        try:
            all_tickets = sprint.list_tickets()
        except Exception:
            all_tickets = []

        if exclude_done:
            filtered = []
            for ticket in all_tickets:
                try:
                    if ticket.status == "done":
                        continue
                except Exception:
                    pass
                filtered.append(ticket)
            all_tickets = filtered

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
        self,
        reader: "StateReader",
        project: "Project",
        exclude_done: bool = False,
    ) -> list[dict]:
        """Iterate all sprints and build the sprints list.

        When *exclude_done* is True, terminal (archived) sprints — see
        :func:`_is_terminal_sprint` — are omitted entirely (and their
        tickets with them, via ``_build_tickets_block``'s own
        ``exclude_done``), so their tickets are never evaluated either.
        This is used ONLY by the status-block hook path —
        ``project.list_sprints()`` itself is unchanged and still returns
        full history including ``done/``, so on-demand callers (MCP
        ``list_sprints``, ``get_sprint_status``) are unaffected.
        """
        try:
            sprints = project.list_sprints()
        except Exception:
            return []

        if exclude_done:
            sprints = [s for s in sprints if not _is_terminal_sprint(s)]

        return [
            self._build_sprint_block(s, reader, exclude_done=exclude_done)
            for s in sprints
        ]

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


# Declared sprint.md ``status:`` values considered terminal/archived.
# Widened (026/007) from ``{"done"}`` alone: the sprint state machine's own
# terminal state is named "closed" (not "done", which is the *ticket*
# machine's terminal state name — see ``sprint.yaml`` vs ``ticket.yaml`` in
# ``clasi.state_machine``), so sprints archived under ``sprints/done/``
# correctly declare ``status: closed`` in frontmatter, not ``status: done``.
_TERMINAL_SPRINT_STATUSES = frozenset({"done", "closed"})


def _is_terminal_sprint(sprint) -> bool:
    """Return True if *sprint* is archived/terminal for sweep purposes.

    Two independent signals are checked so neither alone has to be
    exhaustive or perfectly reliable:

    1. Declared ``status:`` frontmatter matches a known terminal status
       (see :data:`_TERMINAL_SPRINT_STATUSES`).
    2. The sprint directory is physically located under the project's
       ``sprints/done/`` archive directory (``sprint.path.parent.name ==
       "done"``), regardless of what ``status:`` says — directory location
       is itself an authoritative archived signal (``Project.list_sprints``
       is the only writer of that layout), so a sprint whose frontmatter is
       missing, stale, or uses a future terminal label we haven't added to
       (1) yet is still correctly excluded.

    Any error reading either signal (e.g. a malformed frontmatter fetch)
    is swallowed and treated as "not excludable by this signal" — matching
    this module's existing fail-open behaviour for a single sprint's
    exclusion check (an error here should not make the sweep skip a sprint
    that might actually be active).
    """
    try:
        if sprint.status in _TERMINAL_SPRINT_STATUSES:
            return True
    except Exception:
        pass
    try:
        if sprint.path.parent.name == "done":
            return True
    except Exception:
        pass
    return False


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
