"""Inconsistency detection for CLASI status reporting.

This module detects two independent kinds of drift:

- **Sprint stage drift** (as of sprint 030/001): the state-DB
  ``sprints.phase`` value disagrees with the sprint's frontmatter
  ``status:`` field. Both are written together, in one call, by
  ``Sprint.set_sprint_stage()`` — the sole writer of a sprint's recorded
  stage — so the two should always agree; a mismatch here is a genuine
  writer bug, not a stale reader. A sprint physically archived under
  ``sprints/done/`` (or carrying a legacy terminal ``status:`` value —
  see ``status/reporter.py``'s ``_is_terminal_sprint``) is exempt from
  this check regardless of what its DB phase says, which is why none of
  the sprints archived before this vocabulary existed need editing.

  Before sprint 030, this check instead compared frontmatter ``status:``
  against the *computed sprint-machine* state name (the
  ``open``/``planned``/``pre-flight``/… vocabulary) — two vocabularies
  that share only the string ``"closed"`` by construction, so the check
  flagged essentially every healthy sprint. That comparison was a
  category error: the two vocabularies answer different questions —
  "what stage is recorded" vs "what can happen next" — see sprint 030's
  sprint.md Design Rationale. The computed sprint-machine vocabulary is
  not deleted (it still feeds ``available_transitions``/``blocked_by``);
  it is simply no longer compared against frontmatter here.

- **Ticket state drift** (unchanged by sprint 030): a ticket's
  frontmatter ``status:`` field disagrees with the state computed by
  evaluating the ticket state machine's invariants.

Each discrepancy is reported as a ``state_drift`` entry::

    {
        "kind": "state_drift",
        "machine": "sprint",          # or "ticket"
        "id": "001",
        "declared": "planning-docs",  # from frontmatter status:
        "computed": "ticketing",      # sprint: DB phase / ticket: computed ticket-machine state
        "explanation": "sprint.md declares status='planning-docs' but the state database records phase='ticketing'. ..."
    }

The ``explanation`` field differs by machine: for a sprint entry it
states the DB-phase/frontmatter values directly — no state-machine
invariant evaluation is involved, since both sides are the same
recorded-stage vocabulary; for a ticket entry it names the invariant
predicates of the declared state that evaluated to ``False`` (or raised
an exception), unchanged from before.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clasi.project import Project


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_inconsistencies(project: "Project", status_dict: dict) -> list[dict]:
    """Detect sprint stage drift and ticket state drift.

    Iterates every sprint and ticket entry already present in
    *status_dict*. For each non-terminal sprint, compares its frontmatter
    ``status:`` field against the DB's recorded ``sprints.phase`` value
    (see module docstring). For each ticket, compares its frontmatter
    ``status:`` field against the ``state:`` value already computed into
    the ticket entry in *status_dict* (unchanged from before sprint 030).
    Mismatches produce ``state_drift`` entries.

    Artifacts whose frontmatter has no ``status:`` key are skipped (no
    declared state to compare against).  Artifacts whose declared state
    matches the comparison value produce no entry.

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
        # Skip sprints that are terminal/archived (030/001: a directory-
        # location-based check — see _sprint_is_terminal). A terminal
        # sprint has no outbound transitions, so a drift report there has
        # no useful answer — it can't be unblocked or reconciled, only
        # tolerated on read. See
        # detect-inconsistencies-drift-checks-terminal-archived-sprints.
        if not _sprint_is_terminal(project, sprint_id):
            sprint_results = _check_sprint(project, sprint_id)
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


def _sprint_is_terminal(project: "Project", sprint_id: str) -> bool:
    """Return True if *sprint_id* is exempt from stage drift-checking (030/001).

    A sprint physically archived under ``sprints/done/`` is terminal
    regardless of which legacy ``status:`` string it carries — directory
    location, not frontmatter, is the authoritative "is this sprint
    finished" signal. Reuses ``status/reporter.py``'s
    ``_is_terminal_sprint`` (declared-status match OR physical location)
    directly rather than re-implementing a second, differently-shaped
    check that could drift from it.

    Any failure to locate the sprint (e.g. an unregistered or unknown
    sprint_id) is treated as "not terminal" — matching this module's
    existing fail-open behaviour for a single sprint's exclusion check.
    """
    try:
        sprint = project.get_sprint(sprint_id)
    except Exception:
        return False

    from clasi.status.reporter import _is_terminal_sprint

    return _is_terminal_sprint(sprint)


def _check_sprint(project: "Project", sprint_id: str) -> list[dict]:
    """Check a single sprint for DB-phase vs frontmatter status drift (030/001).

    Compares the DB phase (``project.db.get_sprint_state(sprint_id)["phase"]``)
    — the single recorded-stage vocabulary as of sprint 030 — against the
    sprint's frontmatter ``status:`` field, which ``Sprint.set_sprint_stage()``
    writes as the DB phase's exact mirror. The two should always agree; a
    mismatch here is a genuine writer bug, not (as before this sprint) a
    category-error comparison against a differently-scoped computed
    vocabulary.

    Returns a list with at most one ``state_drift`` entry.
    """
    # Read declared status from sprint.md frontmatter.
    declared = _read_sprint_declared_status(project, sprint_id)
    if declared is None:
        return []  # No declared status → nothing to compare

    db_phase = _read_sprint_db_phase(project, sprint_id)
    if db_phase is None:
        return []  # No DB record → nothing to compare (fail-open, matching
        # this module's existing behaviour for a missing signal)

    if declared == db_phase:
        return []  # Consistent — no entry

    explanation = _explain_sprint_drift(project, sprint_id, declared, db_phase)
    return [
        {
            "kind": "state_drift",
            "machine": "sprint",
            "id": sprint_id,
            "declared": declared,
            "computed": db_phase,
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


def _read_sprint_db_phase(project: "Project", sprint_id: str) -> str | None:
    """Return the sprint's DB ``sprints.phase`` value, or None if unavailable.

    None covers: the sprint is not registered in the DB, no DB is present,
    or any other read failure — fail-open, matching
    :func:`_read_sprint_declared_status`'s existing behaviour for a
    missing frontmatter status (no signal to compare means no drift to
    report).
    """
    try:
        state = project.db.get_sprint_state(sprint_id)
        phase = state.get("phase")
        if phase is None:
            return None
        return str(phase)
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


def _explain_sprint_drift(
    project: "Project", sprint_id: str, declared: str, db_phase: str
) -> str:
    """Return a human-readable explanation for a sprint stage drift (030/001).

    Unlike a ticket's explanation (which evaluates ticket-machine
    invariants — a different vocabulary), both sides of a sprint stage
    comparison are the same DB-phase vocabulary, written together by
    ``Sprint.set_sprint_stage()``. No state-machine evaluation is
    involved; the explanation states the two disagreeing values directly.
    """
    return (
        f"sprint.md declares status={declared!r} but the state database "
        f"records phase={db_phase!r} for sprint {sprint_id!r}. Both are "
        "written together by Sprint.set_sprint_stage() and should always "
        "agree — this is a genuine drift, not a stale reader."
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
