"""Sprint-machine predicates for the CLASI state machine engine.

Machine: sprint
Context: :class:`~clasi.state_machine.context.SprintContext`

Note: ``is_on_sprint_branch`` is shared with the project machine and registered
in ``clasi.state_machine.predicates.project``.  When passed a
:class:`~clasi.state_machine.context.SprintContext` it performs an exact branch
match against ``reader.sprint_branch(sprint_id)``.

StateReader methods used:
- ``sprint_artifact_exists(sprint_id, artifact_name)`` — resolves sprint dir by ID-prefix glob
- ``sprint_gate(sprint_id, gate)`` — gate result dict or None (architecture_review, sprint_review)
- ``sprint_flag(sprint_id, flag)`` — sprint flag value (pre_flight_review, post_review)
- ``ticket_count(sprint_id)`` — number of ticket files in the sprint
- ``execution_lock()`` — active lock dict or None
- ``git_branch()`` — current HEAD branch name
- ``sprint_branch(sprint_id)`` — expected branch name for this sprint
- ``all_tickets_done(sprint_id)`` — True if every ticket is done
- ``branch_merged(sprint_id)`` — True if sprint branch is merged into default
"""

from __future__ import annotations

from clasi.state_machine.context import SprintContext
from clasi.state_machine.registry import predicate


@predicate("is_sprint_doc_present")
def is_sprint_doc_present(ctx: SprintContext) -> bool:
    """Return True iff the sprint document exists for this sprint."""
    return ctx.reader.sprint_artifact_exists(ctx.sprint_id, "sprint.md")


@predicate("is_architecture_present")
def is_architecture_present(ctx: SprintContext) -> bool:
    """Return True iff the sprint's architecture-update.md exists."""
    return ctx.reader.sprint_artifact_exists(ctx.sprint_id, "architecture-update.md")


@predicate("is_usecases_present")
def is_usecases_present(ctx: SprintContext) -> bool:
    """Return True iff the sprint's use cases artifact exists."""
    return ctx.reader.sprint_artifact_exists(ctx.sprint_id, "usecases.md")


@predicate("is_architecture_review_recorded")
def is_architecture_review_recorded(ctx: SprintContext) -> bool:
    """Return True iff the state DB has an ``architecture_review`` gate record for this sprint."""
    return ctx.reader.sprint_gate(ctx.sprint_id, "architecture_review") is not None


@predicate("is_pre_flight_satisfied")
def is_pre_flight_satisfied(ctx: SprintContext) -> bool:
    """Return True iff pre-flight is satisfied.

    Satisfied when EITHER the state DB has a ``stakeholder_approval`` gate
    record for this sprint, OR the sprint's ``pre_flight_review`` flag is
    set to ``skip``.  Encodes the pause-or-bump semantics.
    """
    if ctx.reader.sprint_gate(ctx.sprint_id, "stakeholder_approval") is not None:
        return True
    return ctx.reader.sprint_flag(ctx.sprint_id, "pre_flight_review") == "skip"


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


@predicate("is_review_satisfied")
def is_review_satisfied(ctx: SprintContext) -> bool:
    """Return True iff post-execution review is satisfied.

    Satisfied when EITHER the state DB has a ``sprint_review`` gate record
    marked passed, OR the sprint's ``post_review`` flag is set to ``skip``.
    Encodes the pause-or-bump semantics.
    """
    if ctx.reader.sprint_gate(ctx.sprint_id, "sprint_review") is not None:
        return True
    return ctx.reader.sprint_flag(ctx.sprint_id, "post_review") == "skip"


@predicate("is_close_report_present")
def is_close_report_present(ctx: SprintContext) -> bool:
    """Return True iff the sprint's close-report.md exists."""
    return ctx.reader.sprint_artifact_exists(ctx.sprint_id, "close-report.md")


@predicate("is_branch_merged")
def is_branch_merged(ctx: SprintContext) -> bool:
    """Return True iff the sprint branch has been merged into the default branch."""
    return ctx.reader.branch_merged(ctx.sprint_id)
