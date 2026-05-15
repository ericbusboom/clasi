"""Ticket-machine predicates for the CLASI state machine engine.

Machine: ticket
Context: :class:`~clasi.state_machine.context.TicketContext`

StateReader methods used:
- ``file_exists(path)`` — checks ticket file presence
- ``ticket_in_done_dir(sprint_id, ticket_id)`` — True if ticket is in done/ directory
- ``exception_block(sprint_id, ticket_id)`` — exception block dict or None
- ``programmer_dispatched(sprint_id, ticket_id)`` — True if programmer was dispatched
- ``any_sprint_in_phase(phase)`` — True if any sprint (or parent sprint) is executing
- ``dependencies_done(sprint_id, ticket_id)`` — True if all dependency tickets are done
- ``acceptance_criteria_met(sprint_id, ticket_id)`` — True if all checkboxes are checked
- ``tests_passing()`` — True if the test suite passes on the current branch
- ``blocker_identified(sprint_id, ticket_id)`` — True if programmer declared it cannot proceed
- ``blocker_resolved(sprint_id, ticket_id)`` — True if the blocker has been addressed
- ``reopen_requested(sprint_id, ticket_id)`` — True if a reopen_ticket MCP call was made
"""

from __future__ import annotations

from clasi.state_machine.context import TicketContext
from clasi.state_machine.registry import predicate


@predicate("is_ticket_file_present")
def is_ticket_file_present(ctx: TicketContext) -> bool:
    """Return True iff the ticket file exists somewhere under the sprint's tickets/ tree."""
    # Check both the active tickets dir and the done dir.
    active = f"docs/clasi/sprints/{ctx.sprint_id}/tickets/{ctx.ticket_id}.md"
    done = f"docs/clasi/sprints/{ctx.sprint_id}/tickets/done/{ctx.ticket_id}.md"
    return ctx.reader.file_exists(active) or ctx.reader.file_exists(done)


@predicate("is_ticket_in_done_dir")
def is_ticket_in_done_dir(ctx: TicketContext) -> bool:
    """Return True iff the ticket file lives under tickets/done/."""
    return ctx.reader.ticket_in_done_dir(ctx.sprint_id, ctx.ticket_id)


@predicate("is_ticket_not_in_done_dir")
def is_ticket_not_in_done_dir(ctx: TicketContext) -> bool:
    """Return True iff the ticket file does NOT live under tickets/done/."""
    return not ctx.reader.ticket_in_done_dir(ctx.sprint_id, ctx.ticket_id)


@predicate("is_no_exception_block")
def is_no_exception_block(ctx: TicketContext) -> bool:
    """Return True iff the ticket frontmatter has no ``exception:`` block."""
    return ctx.reader.exception_block(ctx.sprint_id, ctx.ticket_id) is None


@predicate("is_exception_block_present")
def is_exception_block_present(ctx: TicketContext) -> bool:
    """Return True iff the ticket frontmatter has an ``exception:`` block."""
    return ctx.reader.exception_block(ctx.sprint_id, ctx.ticket_id) is not None


@predicate("is_programmer_dispatched")
def is_programmer_dispatched(ctx: TicketContext) -> bool:
    """Return True iff a programmer subagent dispatch is recorded for this ticket."""
    return ctx.reader.programmer_dispatched(ctx.sprint_id, ctx.ticket_id)


@predicate("is_sprint_executing")
def is_sprint_executing(ctx: TicketContext) -> bool:
    """Return True iff the parent sprint is in the ``executing`` state."""
    return ctx.reader.sprint_phase(ctx.sprint_id) == "executing"


@predicate("is_dependencies_done")
def is_dependencies_done(ctx: TicketContext) -> bool:
    """Return True iff every ticket listed in this ticket's ``depends-on`` is done."""
    return ctx.reader.dependencies_done(ctx.sprint_id, ctx.ticket_id)


@predicate("is_acceptance_criteria_met")
def is_acceptance_criteria_met(ctx: TicketContext) -> bool:
    """Return True iff every acceptance-criteria checkbox in the ticket body is checked."""
    return ctx.reader.acceptance_criteria_met(ctx.sprint_id, ctx.ticket_id)


@predicate("is_tests_passing")
def is_tests_passing(ctx: TicketContext) -> bool:
    """Return True iff the project's test suite passes on the current branch."""
    return ctx.reader.tests_passing()


@predicate("is_blocker_identified")
def is_blocker_identified(ctx: TicketContext) -> bool:
    """Return True iff the programmer has declared it cannot proceed."""
    return ctx.reader.blocker_identified(ctx.sprint_id, ctx.ticket_id)


@predicate("is_blocker_resolved")
def is_blocker_resolved(ctx: TicketContext) -> bool:
    """Return True iff the blocker recorded in the ticket's exception block has been resolved."""
    return ctx.reader.blocker_resolved(ctx.sprint_id, ctx.ticket_id)


@predicate("is_reopen_requested")
def is_reopen_requested(ctx: TicketContext) -> bool:
    """Return True iff a ``reopen_ticket`` MCP call has been made for this ticket."""
    return ctx.reader.reopen_requested(ctx.sprint_id, ctx.ticket_id)
