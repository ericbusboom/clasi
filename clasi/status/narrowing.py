"""narrowing.py — Agent-scope narrowing for CLASI status dicts.

:func:`narrow_status` takes the full status dict produced by
:class:`~clasi.status.reporter.StatusReporter` (the team-lead view) and
filters it to the scope appropriate for the requesting agent.

Agent scopes
------------

``team-lead``
    Returns the full dict unchanged.

``sprint-planner`` (requires ``sprint_id``)
    Keeps the ``project:`` block, keeps only the matching sprint entry
    under ``sprints:``, removes ``tickets.details`` from that sprint
    (summarized form only), and recomputes ``notes:`` against the narrowed
    scope.  If ``sprint_id`` is not provided, falls back to the broadest
    view the agent can legitimately see (all sprints, no ticket details)
    and adds a ``notes.fallback:`` field explaining the fallback.

``programmer`` (requires ``ticket_id``)
    Keeps the ``project:`` block as read-only context, replaces
    ``sprints:`` with only the parent sprint in summary form (``state``
    and ``id`` only), and sets ``tickets.details`` to the single matching
    ticket entry.  The ``notes:`` block focuses on that ticket's
    transitions.  If ``ticket_id`` is not provided, falls back to
    sprint-planner view (if ``sprint_id`` is known) or team-lead view,
    and adds ``notes.fallback:``.
"""

from __future__ import annotations

import copy
from typing import Any


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def narrow_status(
    full: dict,
    agent: str,
    sprint_id: str | None = None,
    ticket_id: str | None = None,
) -> dict:
    """Narrow *full* to the scope appropriate for *agent*.

    Args:
        full: The complete status dict produced by
            :class:`~clasi.status.reporter.StatusReporter`.
        agent: The requesting agent role.  One of ``"team-lead"``,
            ``"sprint-planner"``, or ``"programmer"``.  Unknown roles
            are treated as ``"team-lead"``.
        sprint_id: Required for ``sprint-planner``; used as a hint for
            ``programmer`` when ``ticket_id`` is absent.
        ticket_id: Required for ``programmer``.  The sprint is inferred
            from the ticket ID format (e.g. ``"006-003"`` → sprint
            ``"006"``).

    Returns:
        A new dict (deep copy of *full*, then filtered) scoped to the
        agent's view.  Never mutates the input.
    """
    if agent == "team-lead":
        return copy.deepcopy(full)

    if agent == "sprint-planner":
        return _narrow_sprint_planner(full, sprint_id)

    if agent == "programmer":
        return _narrow_programmer(full, sprint_id, ticket_id)

    # Unknown agent — treat as team-lead (broadest safe default)
    result = copy.deepcopy(full)
    result["agent"] = agent
    return result


# ---------------------------------------------------------------------------
# sprint-planner narrowing
# ---------------------------------------------------------------------------


def _narrow_sprint_planner(full: dict, sprint_id: str | None) -> dict:
    """Return the sprint-planner view of *full*."""
    result = copy.deepcopy(full)
    result["agent"] = "sprint-planner"

    if sprint_id is None:
        # Fallback: all sprints, but drop ticket details from every sprint
        result["sprints"] = [
            _summarize_sprint_tickets(s) for s in result.get("sprints", [])
        ]
        result["notes"] = _build_notes(result["project"], result["sprints"])
        result["notes"]["fallback"] = (
            "No sprint_id provided; showing all sprints with tickets summarized. "
            "Pass --sprint <id> for a single-sprint view."
        )
        return result

    # Filter to the matching sprint
    matching = [
        s for s in result.get("sprints", []) if s.get("id") == sprint_id
    ]
    narrowed_sprints = [_summarize_sprint_tickets(s) for s in matching]
    result["sprints"] = narrowed_sprints
    result["notes"] = _build_notes(result["project"], narrowed_sprints)
    return result


# ---------------------------------------------------------------------------
# programmer narrowing
# ---------------------------------------------------------------------------


def _narrow_programmer(
    full: dict, sprint_id: str | None, ticket_id: str | None
) -> dict:
    """Return the programmer view of *full*."""
    result = copy.deepcopy(full)
    result["agent"] = "programmer"

    if ticket_id is None:
        # Fallback: sprint-planner view (with or without sprint_id)
        fallback = _narrow_sprint_planner(full, sprint_id)
        fallback["agent"] = "programmer"
        existing_fallback = fallback["notes"].get("fallback", "")
        programmer_note = (
            "No ticket_id provided; falling back to sprint-planner view. "
            "Pass --ticket <id> for a single-ticket programmer view."
        )
        fallback["notes"]["fallback"] = (
            f"{programmer_note} {existing_fallback}".strip()
            if existing_fallback
            else programmer_note
        )
        return fallback

    # Infer sprint_id from ticket_id (format: "<sprint>-<ticket>")
    inferred_sprint_id = _infer_sprint_id(ticket_id, sprint_id)

    # Find the parent sprint and the target ticket detail
    parent_sprint: dict | None = None
    ticket_detail: dict | None = None

    for sprint_entry in result.get("sprints", []):
        if sprint_entry.get("id") == inferred_sprint_id:
            parent_sprint = sprint_entry
            tickets = sprint_entry.get("tickets", {})
            for detail in tickets.get("details", []):
                if detail.get("id") == ticket_id:
                    ticket_detail = detail
                    break
            break

    # Build narrowed sprints: parent sprint in summary form only
    if parent_sprint is not None:
        narrowed_sprint = {
            "id": parent_sprint.get("id"),
            "state": parent_sprint.get("state"),
        }
        if ticket_detail is not None:
            narrowed_sprint["tickets"] = {
                "total": parent_sprint.get("tickets", {}).get("total", 0),
                "by_state": parent_sprint.get("tickets", {}).get("by_state", {}),
                "details": [ticket_detail],
            }
        result["sprints"] = [narrowed_sprint]
    else:
        result["sprints"] = []

    # Recompute notes focused on the ticket
    result["notes"] = _build_programmer_notes(result["project"], result["sprints"], ticket_id)

    return result


# ---------------------------------------------------------------------------
# Helper: strip ticket details from a sprint entry (summarized form)
# ---------------------------------------------------------------------------


def _summarize_sprint_tickets(sprint: dict) -> dict:
    """Return a copy of *sprint* with ``tickets.details`` removed."""
    sprint_copy = copy.deepcopy(sprint)
    tickets = sprint_copy.get("tickets", {})
    tickets.pop("details", None)
    sprint_copy["tickets"] = tickets
    return sprint_copy


# ---------------------------------------------------------------------------
# Helper: infer sprint_id from ticket_id
# ---------------------------------------------------------------------------


def _infer_sprint_id(ticket_id: str, hint: str | None) -> str | None:
    """Infer the sprint ID from *ticket_id* (e.g. ``"006-003"`` → ``"006"``).

    If the ticket_id contains a dash, everything before the last dash is
    used as the sprint prefix.  Falls back to *hint* if parsing fails.
    """
    if "-" in ticket_id:
        parts = ticket_id.rsplit("-", 1)
        if len(parts) == 2 and parts[0]:
            return parts[0]
    return hint


# ---------------------------------------------------------------------------
# Helper: recompute notes from narrowed data
# ---------------------------------------------------------------------------


def _build_notes(project_block: dict, sprints_block: list[dict]) -> dict:
    """Recompute notes from *project_block* and *sprints_block*.

    Mirrors the logic in
    :meth:`~clasi.status.reporter.StatusReporter._build_notes_block`.
    """
    allowed: list[str] = []
    blocked: list[str] = []

    # Project transitions
    for t in project_block.get("available_transitions", []):
        if t.get("fireable"):
            allowed.append(f"Fire `{t['name']}` on project")
        else:
            blockers = t.get("blocked_by", [])
            blocker_str = ", ".join(blockers) if blockers else "unknown"
            blocked.append(
                f"Fire `{t['name']}` on project — blocked by {blocker_str}"
            )

    # Sprint (and ticket) transitions
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

        tickets = sprint_entry.get("tickets", {})
        for ticket_entry in tickets.get("details", []):
            tid = ticket_entry.get("id", "")
            for t in ticket_entry.get("available_transitions", []):
                if t.get("fireable"):
                    allowed.append(f"Fire `{t['name']}` on ticket {tid}")
                else:
                    blockers = t.get("blocked_by", [])
                    blocker_str = ", ".join(blockers) if blockers else "unknown"
                    blocked.append(
                        f"Fire `{t['name']}` on ticket {tid} — blocked by {blocker_str}"
                    )

    focus = _derive_focus(project_block, sprints_block)
    return {
        "current_focus": focus,
        "allowed_next_actions": allowed,
        "blocked_actions": blocked,
    }


def _build_programmer_notes(
    project_block: dict, sprints_block: list[dict], ticket_id: str
) -> dict:
    """Build notes focused on *ticket_id*'s transitions."""
    notes = _build_notes(project_block, sprints_block)

    # Add a focus sentence specific to the ticket
    for sprint_entry in sprints_block:
        tickets = sprint_entry.get("tickets", {})
        for detail in tickets.get("details", []):
            if detail.get("id") == ticket_id:
                t_state = detail.get("state", "unknown")
                notes["current_focus"] = (
                    f"Ticket {ticket_id} is in state: {t_state}"
                )
                return notes

    notes["current_focus"] = f"Ticket {ticket_id} not found in narrowed view"
    return notes


def _derive_focus(project_block: dict, sprints_block: list[dict]) -> str:
    """Return a short sentence about the most actionable current item."""
    for sprint_entry in sprints_block:
        sid = sprint_entry.get("id", "")
        tickets = sprint_entry.get("tickets", {})
        for ticket_entry in tickets.get("details", []):
            if ticket_entry.get("state") == "in-progress":
                tid = ticket_entry.get("id", "")
                return f"Ticket {tid} is in-progress in sprint {sid}"

    for sprint_entry in sprints_block:
        if sprint_entry.get("state") == "executing":
            sid = sprint_entry.get("id", "")
            return f"Sprint {sid} is executing"

    p_state = project_block.get("state", "unknown")
    return f"Project is in state: {p_state}"
