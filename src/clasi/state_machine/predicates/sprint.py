"""Sprint-machine predicates for the CLASI state machine engine.

Machine: sprint
Context: :class:`~clasi.state_machine.context.SprintContext`

Note: ``is_on_sprint_branch`` is shared with the project machine and registered
in ``clasi.state_machine.predicates.project``.  When passed a
:class:`~clasi.state_machine.context.SprintContext` it performs an exact branch
match against ``reader.sprint_branch(sprint_id)``.

StateReader methods used:
- ``sprint_artifact_exists(sprint_id, artifact_name)`` — resolves sprint dir by ID-prefix glob
- ``sprint_gate(sprint_id, gate)`` — gate result dict or None (architecture_review, stakeholder_approval)
- ``ticket_count(sprint_id)`` — number of ticket files in the sprint
- ``execution_lock()`` — active lock dict or None
- ``git_branch()`` — current HEAD branch name
- ``sprint_branch(sprint_id)`` — expected branch name for this sprint
- ``all_tickets_done(sprint_id)`` — True if every ticket is done
- ``branch_merged(sprint_id)`` — True if sprint branch is merged into default
- ``sprint_is_archived(sprint_id)`` — True if the sprint directory lives under sprints/done/
"""

from __future__ import annotations

from clasi.state_machine.context import SprintContext
from clasi.state_machine.registry import predicate


@predicate("is_sprint_doc_present")
def is_sprint_doc_present(ctx: SprintContext) -> bool:
    """Return True iff the sprint document exists for this sprint."""
    return ctx.reader.sprint_artifact_exists(ctx.sprint_id, "sprint.md")


@predicate("is_architecture_review_recorded")
def is_architecture_review_recorded(ctx: SprintContext) -> bool:
    """Return True iff the state DB has a passed or skipped ``architecture_review`` gate record for this sprint.

    Matches ``StateDB.advance_phase``'s own gate semantics
    (``result in {"passed", "skipped"}``) — a **failed** gate record does
    not satisfy this predicate.
    """
    gate = ctx.reader.sprint_gate(ctx.sprint_id, "architecture_review")
    return gate is not None and gate.get("result") in {"passed", "skipped"}


@predicate("is_pre_flight_satisfied")
def is_pre_flight_satisfied(ctx: SprintContext) -> bool:
    """Return True iff the state DB has a passed or skipped ``stakeholder_approval`` gate record for this sprint.

    Matches ``StateDB.advance_phase``'s own gate semantics
    (``result in {"passed", "skipped"}``) — a **failed** gate record does
    not satisfy this predicate. The sprint's ``pre_flight_review``
    frontmatter flag is not consulted: no writer ever sets it, so a
    flag-based fallback can never fire.
    """
    gate = ctx.reader.sprint_gate(ctx.sprint_id, "stakeholder_approval")
    return gate is not None and gate.get("result") in {"passed", "skipped"}


@predicate("is_at_least_one_ticket")
def is_at_least_one_ticket(ctx: SprintContext) -> bool:
    """Return True iff the sprint's tickets directory contains at least one ticket file."""
    return ctx.reader.ticket_count(ctx.sprint_id) > 0


@predicate("is_no_other_sprint_executing")
def is_no_other_sprint_executing(ctx: SprintContext) -> bool:
    """Return True iff no *other* sprint holds the execution lock.

    This sprint itself may or may not hold the lock; what matters is that
    no *different* sprint is executing.
    """
    lock = ctx.reader.execution_lock()
    if lock is None:
        return True
    return lock.get("sprint_id", "") == ctx.sprint_id


@predicate("is_execution_lock_held_by_this_sprint")
def is_execution_lock_held_by_this_sprint(ctx: SprintContext) -> bool:
    """Return True iff the execution lock in the state DB is held by this sprint."""
    lock = ctx.reader.execution_lock()
    if lock is None:
        return False
    return lock.get("sprint_id", "") == ctx.sprint_id


@predicate("is_all_tickets_done")
def is_all_tickets_done(ctx: SprintContext) -> bool:
    """Return True iff every ticket in this sprint is in the ``done`` state."""
    return ctx.reader.all_tickets_done(ctx.sprint_id)


@predicate("is_branch_merged")
def is_branch_merged(ctx: SprintContext) -> bool:
    """Return True iff the sprint branch has been merged into the default branch."""
    return ctx.reader.branch_merged(ctx.sprint_id)


@predicate("is_sprint_archived")
def is_sprint_archived(ctx: SprintContext) -> bool:
    """Return True iff the sprint directory lives under the archive (``sprints/done/``).

    A cheap, git-free, directory-location-based check (030/002 regression
    fix) — see :meth:`~clasi.status.reader.ClasiStateReader.sprint_is_archived`.
    Declared first in the ``closed`` state's invariants so it short-circuits
    ``is_branch_merged`` (which spawns a real ``git`` subprocess) for the
    overwhelmingly common case of an active, non-archived sprint.
    """
    return ctx.reader.sprint_is_archived(ctx.sprint_id)
