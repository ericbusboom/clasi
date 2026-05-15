"""clasi.status — public API for the CLASI status command.

This package bridges the state machine engine (clasi.state_machine) to real
project data (filesystem, git, StateDB) and produces the structured status
output consumed by the CLI command, MCP tool, and auto-injected hook context.

Sprint 006 ticket 001 adds ClasiStateReader and stubs for build_status /
narrow_status. Subsequent tickets fill in the real implementations.
"""

from __future__ import annotations


def build_status(project, agent: str = "team-lead", sprint_id: str | None = None, ticket_id: str | None = None) -> dict:  # noqa: ARG001
    """Build the full status dict for the given project and agent scope.

    .. note::
        Stub implementation — returns an empty dict.
        Sprint 006 ticket 002 (StatusReporter) provides the real implementation.
    """
    return {}


def narrow_status(full: dict, agent: str, sprint_id: str | None = None, ticket_id: str | None = None) -> dict:  # noqa: ARG001
    """Narrow a full status dict to the scope appropriate for *agent*.

    .. note::
        Stub implementation — returns the input dict unchanged.
        Sprint 006 ticket 003 (agent-scope narrowing) provides the real implementation.
    """
    return full


__all__ = ["build_status", "narrow_status"]
