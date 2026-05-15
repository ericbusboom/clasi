"""Project-machine predicates for the CLASI state machine engine.

Machine: project
Context: :class:`~clasi.state_machine.context.ProjectContext`

``is_on_sprint_branch`` is shared with the sprint machine.  When called with a
:class:`~clasi.state_machine.context.ProjectContext` it returns ``True`` if HEAD
is *any* sprint branch (``sprint/*``).  When called with a
:class:`~clasi.state_machine.context.SprintContext` it returns ``True`` only if
HEAD is *this sprint's* specific branch.

StateReader methods used:
- ``file_exists(path)`` — checks for docs/clasi/overview.md
- ``git_branch()`` — current HEAD branch name
- ``default_branch()`` — repository default branch name
- ``sprint_branch(sprint_id)`` — expected branch name for a specific sprint
- ``execution_lock()`` — returns active lock dict or None
- ``any_sprint_in_phase(phase)`` — returns True if any sprint is in the given phase
"""

from __future__ import annotations

from clasi.state_machine.context import ProjectContext, SprintContext
from clasi.state_machine.registry import predicate


@predicate("is_overview_absent")
def is_overview_absent(ctx: ProjectContext) -> bool:
    """Return True iff docs/clasi/overview.md does not exist."""
    return not ctx.reader.file_exists("docs/clasi/overview.md")


@predicate("is_overview_present")
def is_overview_present(ctx: ProjectContext) -> bool:
    """Return True iff docs/clasi/overview.md exists."""
    return ctx.reader.file_exists("docs/clasi/overview.md")


@predicate("is_on_default_branch")
def is_on_default_branch(ctx: ProjectContext) -> bool:
    """Return True iff git HEAD is on the project's default branch (master/main)."""
    branch = ctx.reader.git_branch()
    default = ctx.reader.default_branch()
    return bool(branch) and branch == default


@predicate("is_on_sprint_branch")
def is_on_sprint_branch(ctx: ProjectContext | SprintContext) -> bool:
    """Return True iff git HEAD is on a sprint branch.

    When evaluated against a :class:`ProjectContext`, returns ``True`` if the
    current branch name starts with ``sprint/`` (any sprint).

    When evaluated against a :class:`SprintContext`, returns ``True`` only if the
    current branch matches *this sprint's* designated branch (exact match via
    ``reader.sprint_branch``).
    """
    branch = ctx.reader.git_branch()
    if isinstance(ctx, SprintContext):
        return branch == ctx.reader.sprint_branch(ctx.sprint_id)
    return branch.startswith("sprint/")


@predicate("is_execution_lock_held")
def is_execution_lock_held(ctx: ProjectContext) -> bool:
    """Return True iff the state DB has an active execution lock."""
    return ctx.reader.execution_lock() is not None


@predicate("is_execution_lock_released")
def is_execution_lock_released(ctx: ProjectContext) -> bool:
    """Return True iff no execution lock is currently held."""
    return ctx.reader.execution_lock() is None


@predicate("is_any_sprint_ticketed")
def is_any_sprint_ticketed(ctx: ProjectContext) -> bool:
    """Return True iff at least one sprint is in the ``ticketed`` phase, ready to execute."""
    return ctx.reader.any_sprint_in_phase("ticketed")


@predicate("is_any_sprint_executing")
def is_any_sprint_executing(ctx: ProjectContext) -> bool:
    """Return True iff some sprint is in the ``executing`` phase."""
    return ctx.reader.any_sprint_in_phase("executing")
