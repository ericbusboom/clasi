"""clasi.status — public API for the CLASI status command.

This package bridges the state machine engine (clasi.state_machine) to real
project data (filesystem, git, StateDB) and produces the structured status
output consumed by the CLI command, MCP tool, and auto-injected hook context.

Public API
----------

- :func:`build_status` — build the full status dict for a project.
- :func:`narrow_status` — filter a full dict to an agent's scope (ticket 003).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clasi.project import Project
    from clasi.state_machine.context import StateReader


def build_status(
    project: "Project",
    agent: str = "team-lead",
    sprint_id: str | None = None,
    ticket_id: str | None = None,
    reader: "StateReader | None" = None,
) -> dict:
    """Build the full status dict for *project*.

    Instantiates :class:`~clasi.status.reporter.StatusReporter` with
    :class:`~clasi.status.reader.ClasiStateReader` (unless *reader* is
    supplied) and delegates to :meth:`~clasi.status.reporter.StatusReporter.build`.

    Args:
        project: The CLASI project to evaluate.
        agent: Requesting agent name; stored verbatim in the output.
        sprint_id: Optional sprint ID hint passed through to the reporter.
        ticket_id: Optional ticket ID hint passed through to the reporter.
        reader: Optional :class:`~clasi.state_machine.context.StateReader`
            override (useful for testing with :class:`~clasi.state_machine.context.NullStateReader`).

    Returns:
        A dict with top-level keys: ``agent``, ``computed_at``, ``project``,
        ``sprints``, ``issues``, ``notes``, ``inconsistencies``.
    """
    from clasi.status.reporter import StatusReporter

    return StatusReporter(project, reader=reader).build(
        agent=agent, sprint_id=sprint_id, ticket_id=ticket_id
    )


def narrow_status(full: dict, agent: str, sprint_id: str | None = None, ticket_id: str | None = None) -> dict:  # noqa: ARG001
    """Narrow a full status dict to the scope appropriate for *agent*.

    .. note::
        Stub implementation — returns the input dict unchanged.
        Sprint 006 ticket 003 (agent-scope narrowing) provides the real implementation.
    """
    return full


__all__ = ["build_status", "narrow_status"]
