"""Unit tests for clasi.state_machine.context.

Verifies construction of each context type using NullStateReader, field
access, and protocol compliance.
"""

from __future__ import annotations

import pytest

from clasi.state_machine.context import (
    NullStateReader,
    ProjectContext,
    SprintContext,
    StateReader,
    TicketContext,
)


# ---------------------------------------------------------------------------
# NullStateReader
# ---------------------------------------------------------------------------


class TestNullStateReader:
    def setup_method(self):
        self.reader = NullStateReader()

    def test_file_exists_returns_false(self):
        assert self.reader.file_exists("/any/path") is False

    def test_git_branch_returns_empty_string(self):
        assert self.reader.git_branch() == ""

    def test_default_branch_returns_empty_string(self):
        assert self.reader.default_branch() == ""

    def test_execution_lock_returns_none(self):
        assert self.reader.execution_lock() is None

    def test_sprint_phase_returns_empty_string(self):
        assert self.reader.sprint_phase("001") == ""

    def test_sprint_gate_returns_none(self):
        assert self.reader.sprint_gate("001", "pre_execution") is None

    def test_sprint_branch_returns_empty_string(self):
        assert self.reader.sprint_branch("001") == ""

    def test_ticket_status_returns_empty_string(self):
        assert self.reader.ticket_status("001", "001-001") == ""

    def test_all_tickets_done_returns_false(self):
        assert self.reader.all_tickets_done("001") is False

    def test_ticket_in_done_dir_returns_false(self):
        assert self.reader.ticket_in_done_dir("001", "001-001") is False

    def test_exception_block_returns_none(self):
        assert self.reader.exception_block("001", "001-001") is None

    def test_programmer_dispatched_returns_false(self):
        assert self.reader.programmer_dispatched("001", "001-001") is False

    def test_sprint_flag_returns_empty_string(self):
        assert self.reader.sprint_flag("001", "pre_flight_review") == ""

    def test_branch_merged_returns_false(self):
        assert self.reader.branch_merged("001") is False

    def test_sprint_is_archived_returns_false(self):
        assert self.reader.sprint_is_archived("001") is False

    def test_dependencies_done_returns_false(self):
        assert self.reader.dependencies_done("001", "001-001") is False

    def test_acceptance_criteria_met_returns_false(self):
        assert self.reader.acceptance_criteria_met("001", "001-001") is False

    def test_tests_passing_returns_false(self):
        assert self.reader.tests_passing() is False

    def test_blocker_identified_returns_false(self):
        assert self.reader.blocker_identified("001", "001-001") is False

    def test_blocker_resolved_returns_false(self):
        assert self.reader.blocker_resolved("001", "001-001") is False

    def test_reopen_requested_returns_false(self):
        assert self.reader.reopen_requested("001", "001-001") is False

    def test_any_sprint_in_phase_returns_false(self):
        assert self.reader.any_sprint_in_phase("executing") is False

    def test_ticket_count_returns_zero(self):
        assert self.reader.ticket_count("001") == 0

    def test_satisfies_state_reader_protocol(self):
        """NullStateReader must satisfy the StateReader protocol at runtime."""
        assert isinstance(self.reader, StateReader)


# ---------------------------------------------------------------------------
# ProjectContext
# ---------------------------------------------------------------------------


class TestProjectContext:
    def test_construction(self):
        reader = NullStateReader()
        ctx = ProjectContext(reader=reader)
        assert ctx.reader is reader

    def test_reader_field_is_accessible(self):
        reader = NullStateReader()
        ctx = ProjectContext(reader=reader)
        # Can call methods via the context's reader
        assert ctx.reader.git_branch() == ""

    def test_reader_field_is_mutable(self):
        """ProjectContext is a plain dataclass — fields are mutable."""
        reader1 = NullStateReader()
        reader2 = NullStateReader()
        ctx = ProjectContext(reader=reader1)
        ctx.reader = reader2
        assert ctx.reader is reader2


# ---------------------------------------------------------------------------
# SprintContext
# ---------------------------------------------------------------------------


class TestSprintContext:
    def test_construction(self):
        reader = NullStateReader()
        proj = ProjectContext(reader=reader)
        ctx = SprintContext(sprint_id="005", reader=reader, project=proj)
        assert ctx.sprint_id == "005"
        assert ctx.reader is reader
        assert ctx.project is proj

    def test_project_field_references_project_context(self):
        reader = NullStateReader()
        proj = ProjectContext(reader=reader)
        ctx = SprintContext(sprint_id="001", reader=reader, project=proj)
        assert isinstance(ctx.project, ProjectContext)

    def test_reader_accessible_through_sprint_context(self):
        reader = NullStateReader()
        proj = ProjectContext(reader=reader)
        ctx = SprintContext(sprint_id="001", reader=reader, project=proj)
        assert ctx.reader.sprint_phase("001") == ""


# ---------------------------------------------------------------------------
# TicketContext
# ---------------------------------------------------------------------------


class TestTicketContext:
    def _make_ticket_context(
        self,
        ticket_id: str = "005-004",
        sprint_id: str = "005",
    ) -> TicketContext:
        reader = NullStateReader()
        proj = ProjectContext(reader=reader)
        sprint = SprintContext(sprint_id=sprint_id, reader=reader, project=proj)
        return TicketContext(
            ticket_id=ticket_id,
            sprint_id=sprint_id,
            reader=reader,
            sprint=sprint,
        )

    def test_construction(self):
        ctx = self._make_ticket_context()
        assert ctx.ticket_id == "005-004"
        assert ctx.sprint_id == "005"
        assert isinstance(ctx.reader, StateReader)
        assert isinstance(ctx.sprint, SprintContext)

    def test_sprint_field_references_sprint_context(self):
        ctx = self._make_ticket_context()
        assert ctx.sprint.sprint_id == "005"

    def test_sprint_links_to_project(self):
        ctx = self._make_ticket_context()
        assert isinstance(ctx.sprint.project, ProjectContext)

    def test_reader_accessible_through_ticket_context(self):
        ctx = self._make_ticket_context()
        assert ctx.reader.ticket_status("005", "005-004") == ""

    def test_exception_block_via_reader(self):
        ctx = self._make_ticket_context()
        assert ctx.reader.exception_block("005", "005-004") is None

    def test_different_ticket_ids(self):
        ctx = self._make_ticket_context(ticket_id="001-003", sprint_id="001")
        assert ctx.ticket_id == "001-003"
        assert ctx.sprint_id == "001"


# ---------------------------------------------------------------------------
# Protocol compliance with custom mock
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """Verify that any object implementing all StateReader methods satisfies it."""

    def test_custom_reader_satisfies_protocol(self):
        class CustomReader:
            def file_exists(self, path: str) -> bool:
                return True

            def git_branch(self) -> str:
                return "main"

            def default_branch(self) -> str:
                return "main"

            def execution_lock(self) -> dict | None:
                return {"holder": "test"}

            def sprint_phase(self, sprint_id: str) -> str:
                return "executing"

            def sprint_gate(self, sprint_id: str, gate: str) -> dict | None:
                return None

            def sprint_branch(self, sprint_id: str) -> str:
                return f"sprint/{sprint_id}"

            def ticket_status(self, sprint_id: str, ticket_id: str) -> str:
                return "done"

            def all_tickets_done(self, sprint_id: str) -> bool:
                return True

            def ticket_in_done_dir(self, sprint_id: str, ticket_id: str) -> bool:
                return True

            def exception_block(self, sprint_id: str, ticket_id: str) -> dict | None:
                return None

            def programmer_dispatched(self, sprint_id: str, ticket_id: str) -> bool:
                return True

            def sprint_flag(self, sprint_id: str, flag: str) -> str:
                return ""

            def branch_merged(self, sprint_id: str) -> bool:
                return False

            def sprint_is_archived(self, sprint_id: str) -> bool:
                return False

            def dependencies_done(self, sprint_id: str, ticket_id: str) -> bool:
                return False

            def acceptance_criteria_met(self, sprint_id: str, ticket_id: str) -> bool:
                return False

            def tests_passing(self) -> bool:
                return False

            def blocker_identified(self, sprint_id: str, ticket_id: str) -> bool:
                return False

            def blocker_resolved(self, sprint_id: str, ticket_id: str) -> bool:
                return False

            def reopen_requested(self, sprint_id: str, ticket_id: str) -> bool:
                return False

            def any_sprint_in_phase(self, phase: str) -> bool:
                return False

            def ticket_count(self, sprint_id: str) -> int:
                return 0

            def overview_exists(self) -> bool:
                return False

            def sprint_artifact_exists(self, sprint_id: str, artifact_name: str) -> bool:
                return False

            def ticket_file_present(self, sprint_id: str, ticket_id: str) -> bool:
                return False

        reader = CustomReader()
        assert isinstance(reader, StateReader)

    def test_incomplete_reader_does_not_satisfy_protocol(self):
        class IncompleteReader:
            def file_exists(self, path: str) -> bool:
                return False
            # missing other methods

        reader = IncompleteReader()
        assert not isinstance(reader, StateReader)
