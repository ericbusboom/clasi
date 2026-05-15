"""Context dataclasses and StateReader protocol for the CLASI state machine engine.

Context objects are passed to every predicate call. Each context holds
a reference to a :class:`StateReader` — the narrow interface through which
predicates access external state (filesystem, git, SQLite DB) without
performing I/O themselves.

Sprint 006 provides the production implementation of :class:`StateReader`
(:class:`StateReaderImpl` wired to the actual filesystem and StateDB).
Sprint 005 tests use :class:`NullStateReader` to avoid real I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# StateReader protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class StateReader(Protocol):
    """Read-only interface for predicate access to external state.

    All methods are **read-only** — the protocol has no write methods, so
    predicates are pure by construction.

    Sprint 006 provides the production implementation.
    Sprint 005 tests use :class:`NullStateReader`.
    """

    def file_exists(self, path: str) -> bool:
        """Return True if *path* exists on the filesystem."""
        ...

    def git_branch(self) -> str:
        """Return the current git branch name."""
        ...

    def default_branch(self) -> str:
        """Return the repository's default/main branch name."""
        ...

    def execution_lock(self) -> dict | None:
        """Return the execution lock dict if one is held, else None."""
        ...

    def sprint_phase(self, sprint_id: str) -> str:
        """Return the current phase string for *sprint_id*."""
        ...

    def sprint_gate(self, sprint_id: str, gate: str) -> dict | None:
        """Return the gate result dict for *sprint_id* / *gate*, or None."""
        ...

    def sprint_branch(self, sprint_id: str) -> str:
        """Return the git branch name associated with *sprint_id*."""
        ...

    def ticket_status(self, sprint_id: str, ticket_id: str) -> str:
        """Return the status string for the given ticket."""
        ...

    def all_tickets_done(self, sprint_id: str) -> bool:
        """Return True if every ticket in *sprint_id* has status ``done``."""
        ...

    def ticket_in_done_dir(self, sprint_id: str, ticket_id: str) -> bool:
        """Return True if the ticket file has been moved to the done directory."""
        ...

    def exception_block(self, sprint_id: str, ticket_id: str) -> dict | None:
        """Return the exception block dict for *ticket_id*, or None."""
        ...

    def programmer_dispatched(self, sprint_id: str, ticket_id: str) -> bool:
        """Return True if a programmer agent has been dispatched for *ticket_id*."""
        ...


# ---------------------------------------------------------------------------
# NullStateReader — safe defaults for unit tests
# ---------------------------------------------------------------------------


class NullStateReader:
    """A no-op implementation of :class:`StateReader` for unit tests.

    Every bool method returns ``False``.
    Every method returning ``str`` returns ``""``.
    Every method returning ``dict | None`` returns ``None``.
    Every method returning a list returns ``[]``.

    This satisfies the :class:`StateReader` protocol structurally, so it can
    be injected wherever a real reader is expected — without touching the
    filesystem, git, or the database.
    """

    def file_exists(self, path: str) -> bool:
        return False

    def git_branch(self) -> str:
        return ""

    def default_branch(self) -> str:
        return ""

    def execution_lock(self) -> dict | None:
        return None

    def sprint_phase(self, sprint_id: str) -> str:
        return ""

    def sprint_gate(self, sprint_id: str, gate: str) -> dict | None:
        return None

    def sprint_branch(self, sprint_id: str) -> str:
        return ""

    def ticket_status(self, sprint_id: str, ticket_id: str) -> str:
        return ""

    def all_tickets_done(self, sprint_id: str) -> bool:
        return False

    def ticket_in_done_dir(self, sprint_id: str, ticket_id: str) -> bool:
        return False

    def exception_block(self, sprint_id: str, ticket_id: str) -> dict | None:
        return None

    def programmer_dispatched(self, sprint_id: str, ticket_id: str) -> bool:
        return False


# ---------------------------------------------------------------------------
# Context dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ProjectContext:
    """Context for project-level predicate evaluation.

    Attributes:
        reader: The :class:`StateReader` used to answer predicate questions.
    """

    reader: StateReader


@dataclass
class SprintContext:
    """Context for sprint-level predicate evaluation.

    Attributes:
        sprint_id: The sprint identifier (e.g. ``"005"``).
        reader: The :class:`StateReader` used to answer predicate questions.
        project: The containing :class:`ProjectContext`.
    """

    sprint_id: str
    reader: StateReader
    project: ProjectContext


@dataclass
class TicketContext:
    """Context for ticket-level predicate evaluation.

    Attributes:
        ticket_id: The ticket identifier (e.g. ``"005-004"``).
        sprint_id: The sprint identifier (e.g. ``"005"``).
        reader: The :class:`StateReader` used to answer predicate questions.
        sprint: The containing :class:`SprintContext`.
    """

    ticket_id: str
    sprint_id: str
    reader: StateReader
    sprint: SprintContext
