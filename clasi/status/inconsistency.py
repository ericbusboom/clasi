"""Inconsistency detection for CLASI status reporting.

This module detects state drift: cases where an artifact's frontmatter
``status:`` field disagrees with the state computed by the state machine
engine.

Each discrepancy is reported as a ``state_drift`` entry::

    {
        "kind": "state_drift",
        "machine": "sprint",        # or "ticket"
        "id": "001",
        "declared": "planned",      # from frontmatter status:
        "computed": "open",         # from state machine evaluation
        "explanation": "sprint.md declares status=planned but is_architecture_present is False."
    }

The ``explanation`` field names the invariant predicates of the declared
state that evaluated to ``False`` (or raised an exception), explaining why
the declared state does not hold.  If the declared state name is not
recognised by the machine, the explanation notes that instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clasi.project import Project


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_inconsistencies(project: "Project", status_dict: dict) -> list[dict]:
    """Compare declared ``status:`` frontmatter against computed ``state:`` values.

    Iterates every sprint and ticket entry already present in *status_dict*,
    reads the corresponding artifact's frontmatter ``status:`` field, and
    compares it against the ``state:`` value in the dict.  Mismatches produce
    ``state_drift`` entries.

    Artifacts whose frontmatter has no ``status:`` key are skipped (no
    declared state to compare against).  Artifacts whose declared state
    matches the computed state produce no entry.

    Args:
        project: The CLASI :class:`~clasi.project.Project` whose artifacts
            are being inspected.  Used to locate sprint.md and ticket files
            and to build state-machine contexts for the explanation.
        status_dict: The full status dict assembled by
            :class:`~clasi.status.reporter.StatusReporter`.  Must contain a
            ``"sprints"`` key with the standard sprint-entry shape.

    Returns:
        A (possibly empty) list of ``state_drift`` dicts, one per
        inconsistent artifact.
    """
    results: list[dict] = []

    for sprint_entry in status_dict.get("sprints", []):
        sprint_id = sprint_entry.get("id", "")
        if not sprint_id:
            continue

        # --- Sprint inconsistency check ---
        sprint_results = _check_sprint(project, sprint_id, sprint_entry)
        results.extend(sprint_results)

        # --- Ticket inconsistency checks ---
        tickets_block = sprint_entry.get("tickets", {})
        for ticket_entry in tickets_block.get("details", []):
            ticket_id = ticket_entry.get("id", "")
            if not ticket_id:
                continue
            ticket_results = _check_ticket(project, sprint_id, ticket_id, ticket_entry)
            results.extend(ticket_results)

    return results


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _check_sprint(project: "Project", sprint_id: str, sprint_entry: dict) -> list[dict]:
    """Check a single sprint for declared vs computed state drift.

    Returns a list with at most one ``state_drift`` entry.
    """
    computed = sprint_entry.get("state", "")

    # Read declared status from sprint.md frontmatter.
    declared = _read_sprint_declared_status(project, sprint_id)
    if declared is None:
        return []  # No declared status → nothing to compare

    if declared == computed:
        return []  # Consistent — no entry

    explanation = _explain_sprint_drift(project, sprint_id, declared)
    return [
        {
            "kind": "state_drift",
            "machine": "sprint",
            "id": sprint_id,
            "declared": declared,
            "computed": computed,
            "explanation": explanation,
        }
    ]


def _check_ticket(
    project: "Project",
    sprint_id: str,
    ticket_id: str,
    ticket_entry: dict,
) -> list[dict]:
    """Check a single ticket for declared vs computed state drift.

    Returns a list with at most one ``state_drift`` entry.
    """
    computed = ticket_entry.get("state", "")

    # Read declared status from ticket frontmatter.
    declared = _read_ticket_declared_status(project, sprint_id, ticket_id)
    if declared is None:
        return []  # No declared status → nothing to compare

    if declared == computed:
        return []  # Consistent — no entry

    explanation = _explain_ticket_drift(project, sprint_id, ticket_id, declared)
    return [
        {
            "kind": "state_drift",
            "machine": "ticket",
            "id": ticket_id,
            "declared": declared,
            "computed": computed,
            "explanation": explanation,
        }
    ]


# ---------------------------------------------------------------------------
# Frontmatter readers
# ---------------------------------------------------------------------------


def _read_sprint_declared_status(project: "Project", sprint_id: str) -> str | None:
    """Return the sprint.md ``status:`` frontmatter value, or None if absent."""
    try:
        sprint = project.get_sprint(sprint_id)
        fm = sprint.sprint_doc.frontmatter
        status = fm.get("status")
        if status is None:
            return None
        return str(status)
    except Exception:
        return None


def _read_ticket_declared_status(
    project: "Project", sprint_id: str, ticket_id: str
) -> str | None:
    """Return a ticket's ``status:`` frontmatter value, or None if absent."""
    try:
        sprint = project.get_sprint(sprint_id)
        from clasi.frontmatter import read_frontmatter

        for location in [sprint.tickets_dir, sprint.tickets_done_dir]:
            try:
                if not location.exists():
                    continue
                for f in location.glob("*.md"):
                    if f.stem.startswith(ticket_id + "-") or f.stem == ticket_id:
                        fm = read_frontmatter(f)
                        if fm.get("id") == ticket_id:
                            status = fm.get("status")
                            if status is None:
                                return None
                            return str(status)
            except Exception:
                continue
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Explanation builders
# ---------------------------------------------------------------------------


def _explain_sprint_drift(project: "Project", sprint_id: str, declared: str) -> str:
    """Return a human-readable explanation for a sprint state drift.

    Evaluates the invariant predicates of the *declared* state against a
    live sprint context.  Lists predicates that returned ``False`` or raised
    an exception.  If the declared state is not known to the machine, reports
    that instead.
    """
    try:
        from clasi.state_machine import (
            ProjectContext,
            SprintContext,
            evaluate_predicates,
            load_machine,
        )
        from clasi.status.reader import ClasiStateReader

        reader = ClasiStateReader(project)
        machine = load_machine("sprint")

        if declared not in machine.states:
            return (
                f"Declared state {declared!r} is not a recognised sprint machine state. "
                f"Known states: {list(machine.states.keys())}."
            )

        invariants = list(machine.states[declared].invariants)
        if not invariants:
            return (
                f"Declared state {declared!r} has no invariants — "
                "cannot determine why it does not hold."
            )

        project_ctx = ProjectContext(reader=reader)
        sprint_ctx = SprintContext(
            sprint_id=sprint_id, reader=reader, project=project_ctx
        )
        results = evaluate_predicates(invariants, sprint_ctx)

        failing = [
            name
            for name, outcome in results.items()
            if outcome is not True
        ]
        if not failing:
            return (
                f"sprint.md declares status={declared!r} but the state machine "
                "does not compute that state (no failing invariants identified)."
            )

        failing_str = ", ".join(failing)
        return (
            f"sprint.md declares status={declared!r} but "
            f"{failing_str} "
            f"{'is' if len(failing) == 1 else 'are'} False."
        )
    except Exception as exc:
        return (
            f"sprint.md declares status={declared!r} but the computed state "
            f"disagrees (explanation unavailable: {exc})."
        )


def _explain_ticket_drift(
    project: "Project", sprint_id: str, ticket_id: str, declared: str
) -> str:
    """Return a human-readable explanation for a ticket state drift.

    Evaluates the invariant predicates of the *declared* state against a
    live ticket context.  Lists predicates that returned ``False`` or raised.
    """
    try:
        from clasi.state_machine import (
            ProjectContext,
            SprintContext,
            TicketContext,
            evaluate_predicates,
            load_machine,
        )
        from clasi.status.reader import ClasiStateReader

        reader = ClasiStateReader(project)
        machine = load_machine("ticket")

        if declared not in machine.states:
            return (
                f"Declared state {declared!r} is not a recognised ticket machine state. "
                f"Known states: {list(machine.states.keys())}."
            )

        invariants = list(machine.states[declared].invariants)
        if not invariants:
            return (
                f"Declared state {declared!r} has no invariants — "
                "cannot determine why it does not hold."
            )

        project_ctx = ProjectContext(reader=reader)
        sprint_ctx = SprintContext(
            sprint_id=sprint_id, reader=reader, project=project_ctx
        )
        ticket_ctx = TicketContext(
            ticket_id=ticket_id,
            sprint_id=sprint_id,
            reader=reader,
            sprint=sprint_ctx,
        )
        results = evaluate_predicates(invariants, ticket_ctx)

        failing = [
            name
            for name, outcome in results.items()
            if outcome is not True
        ]
        if not failing:
            return (
                f"Ticket declares status={declared!r} but the state machine "
                "does not compute that state (no failing invariants identified)."
            )

        failing_str = ", ".join(failing)
        return (
            f"Ticket declares status={declared!r} but "
            f"{failing_str} "
            f"{'is' if len(failing) == 1 else 'are'} False."
        )
    except Exception as exc:
        return (
            f"Ticket declares status={declared!r} but the computed state "
            f"disagrees (explanation unavailable: {exc})."
        )
