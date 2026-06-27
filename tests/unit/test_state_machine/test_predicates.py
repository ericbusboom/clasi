"""Unit tests for clasi.state_machine.predicates.

Covers True and False cases for all 34 predicates:
- 8 project predicates
- 13 sprint predicates  (is_on_sprint_branch shared with project)
- 13 ticket predicates

Uses ``unittest.mock.MagicMock`` or stub readers to keep tests isolated
from the filesystem, git, and the database.

The ``_clean_registry`` fixture clears the global registry before and after
every test.  Importing ``clasi.state_machine.predicates`` inside the fixture
(after clear) re-registers predicates for each test.
"""

from __future__ import annotations

import importlib
import pytest
from unittest.mock import MagicMock

from clasi.state_machine.registry import clear_registry
from clasi.state_machine.context import (
    NullStateReader,
    ProjectContext,
    SprintContext,
    TicketContext,
)
import clasi.state_machine.predicates
import clasi.state_machine.predicates.project
import clasi.state_machine.predicates.sprint
import clasi.state_machine.predicates.ticket


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    """Clear the registry before each test, then reload predicate modules to re-register.

    ``@predicate`` decorators run at import time.  Since Python caches modules
    after the first import, we must explicitly reload each module to re-trigger
    registration after ``clear_registry()``.  Import order matters: ``project``
    must be reloaded before ``sprint`` because ``sprint`` depends on
    ``is_on_sprint_branch`` already being registered.
    """
    clear_registry()
    importlib.reload(clasi.state_machine.predicates.project)
    importlib.reload(clasi.state_machine.predicates.sprint)
    importlib.reload(clasi.state_machine.predicates.ticket)
    yield
    clear_registry()


def _project_ctx(reader=None) -> ProjectContext:
    return ProjectContext(reader=reader or NullStateReader())


def _sprint_ctx(sprint_id: str = "005", reader=None) -> SprintContext:
    r = reader or NullStateReader()
    proj = ProjectContext(reader=r)
    return SprintContext(sprint_id=sprint_id, reader=r, project=proj)


def _ticket_ctx(
    ticket_id: str = "005-001",
    sprint_id: str = "005",
    reader=None,
) -> TicketContext:
    r = reader or NullStateReader()
    proj = ProjectContext(reader=r)
    sprint = SprintContext(sprint_id=sprint_id, reader=r, project=proj)
    return TicketContext(
        ticket_id=ticket_id,
        sprint_id=sprint_id,
        reader=r,
        sprint=sprint,
    )


def _mock_reader(**kwargs) -> MagicMock:
    """Return a MagicMock with all StateReader methods defaulting to safe values."""
    reader = MagicMock()
    # Sensible defaults matching NullStateReader
    reader.file_exists.return_value = False
    reader.git_branch.return_value = ""
    reader.default_branch.return_value = ""
    reader.execution_lock.return_value = None
    reader.sprint_phase.return_value = ""
    reader.sprint_gate.return_value = None
    reader.sprint_branch.return_value = ""
    reader.ticket_status.return_value = ""
    reader.all_tickets_done.return_value = False
    reader.ticket_in_done_dir.return_value = False
    reader.exception_block.return_value = None
    reader.programmer_dispatched.return_value = False
    reader.sprint_flag.return_value = ""
    reader.branch_merged.return_value = False
    reader.dependencies_done.return_value = False
    reader.acceptance_criteria_met.return_value = False
    reader.tests_passing.return_value = False
    reader.blocker_identified.return_value = False
    reader.blocker_resolved.return_value = False
    reader.reopen_requested.return_value = False
    reader.any_sprint_in_phase.return_value = False
    reader.ticket_count.return_value = 0
    reader.overview_exists.return_value = False
    reader.sprint_artifact_exists.return_value = False
    reader.ticket_file_present.return_value = False

    # Apply any overrides from kwargs
    for attr, val in kwargs.items():
        getattr(reader, attr).return_value = val
    return reader


# ---------------------------------------------------------------------------
# Project predicates (8)
# ---------------------------------------------------------------------------


class TestIsOverviewAbsent:
    def test_true_when_overview_missing(self):
        reader = _mock_reader(overview_exists=False)
        ctx = _project_ctx(reader)
        from clasi.state_machine.predicates.project import is_overview_absent
        assert is_overview_absent(ctx) is True

    def test_false_when_overview_present(self):
        reader = _mock_reader(overview_exists=True)
        ctx = _project_ctx(reader)
        from clasi.state_machine.predicates.project import is_overview_absent
        assert is_overview_absent(ctx) is False


class TestIsOverviewPresent:
    def test_true_when_overview_exists(self):
        reader = _mock_reader(overview_exists=True)
        ctx = _project_ctx(reader)
        from clasi.state_machine.predicates.project import is_overview_present
        assert is_overview_present(ctx) is True

    def test_false_when_overview_missing(self):
        reader = _mock_reader(overview_exists=False)
        ctx = _project_ctx(reader)
        from clasi.state_machine.predicates.project import is_overview_present
        assert is_overview_present(ctx) is False


class TestIsOnDefaultBranch:
    def test_true_when_on_default_branch(self):
        reader = _mock_reader()
        reader.git_branch.return_value = "master"
        reader.default_branch.return_value = "master"
        ctx = _project_ctx(reader)
        from clasi.state_machine.predicates.project import is_on_default_branch
        assert is_on_default_branch(ctx) is True

    def test_false_when_on_different_branch(self):
        reader = _mock_reader()
        reader.git_branch.return_value = "sprint/005-state-machine"
        reader.default_branch.return_value = "master"
        ctx = _project_ctx(reader)
        from clasi.state_machine.predicates.project import is_on_default_branch
        assert is_on_default_branch(ctx) is False

    def test_false_when_branch_empty(self):
        reader = _mock_reader()
        reader.git_branch.return_value = ""
        reader.default_branch.return_value = "master"
        ctx = _project_ctx(reader)
        from clasi.state_machine.predicates.project import is_on_default_branch
        assert is_on_default_branch(ctx) is False


class TestIsOnSprintBranchProject:
    """Project-context variant: any sprint branch (starts with 'sprint/')."""

    def test_true_when_on_sprint_branch(self):
        reader = _mock_reader()
        reader.git_branch.return_value = "sprint/005-state-machine"
        ctx = _project_ctx(reader)
        from clasi.state_machine.predicates.project import is_on_sprint_branch
        assert is_on_sprint_branch(ctx) is True

    def test_false_when_on_master(self):
        reader = _mock_reader()
        reader.git_branch.return_value = "master"
        ctx = _project_ctx(reader)
        from clasi.state_machine.predicates.project import is_on_sprint_branch
        assert is_on_sprint_branch(ctx) is False

    def test_false_when_branch_empty(self):
        ctx = _project_ctx()  # NullStateReader returns ""
        from clasi.state_machine.predicates.project import is_on_sprint_branch
        assert is_on_sprint_branch(ctx) is False


class TestIsOnSprintBranchSprint:
    """Sprint-context variant: must match this sprint's specific branch."""

    def test_true_when_on_this_sprint_branch(self):
        reader = _mock_reader()
        reader.git_branch.return_value = "sprint/005-state-machine"
        reader.sprint_branch.return_value = "sprint/005-state-machine"
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.project import is_on_sprint_branch
        assert is_on_sprint_branch(ctx) is True

    def test_false_when_on_different_sprint_branch(self):
        reader = _mock_reader()
        reader.git_branch.return_value = "sprint/004-something-else"
        reader.sprint_branch.return_value = "sprint/005-state-machine"
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.project import is_on_sprint_branch
        assert is_on_sprint_branch(ctx) is False

    def test_false_when_on_master(self):
        reader = _mock_reader()
        reader.git_branch.return_value = "master"
        reader.sprint_branch.return_value = "sprint/005-state-machine"
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.project import is_on_sprint_branch
        assert is_on_sprint_branch(ctx) is False


class TestIsExecutionLockHeld:
    def test_true_when_lock_is_held(self):
        reader = _mock_reader(execution_lock={"sprint_id": "005"})
        # execution_lock is a method returning dict, need to set differently
        reader2 = _mock_reader()
        reader2.execution_lock.return_value = {"sprint_id": "005"}
        ctx = _project_ctx(reader2)
        from clasi.state_machine.predicates.project import is_execution_lock_held
        assert is_execution_lock_held(ctx) is True

    def test_false_when_no_lock(self):
        ctx = _project_ctx()  # NullStateReader returns None
        from clasi.state_machine.predicates.project import is_execution_lock_held
        assert is_execution_lock_held(ctx) is False


class TestIsExecutionLockReleased:
    def test_true_when_no_lock(self):
        ctx = _project_ctx()  # NullStateReader returns None
        from clasi.state_machine.predicates.project import is_execution_lock_released
        assert is_execution_lock_released(ctx) is True

    def test_false_when_lock_is_held(self):
        reader = _mock_reader()
        reader.execution_lock.return_value = {"sprint_id": "005"}
        ctx = _project_ctx(reader)
        from clasi.state_machine.predicates.project import is_execution_lock_released
        assert is_execution_lock_released(ctx) is False


class TestIsAnySprintTicketed:
    def test_true_when_sprint_in_ticketed_phase(self):
        reader = _mock_reader()
        reader.any_sprint_in_phase.return_value = True
        ctx = _project_ctx(reader)
        from clasi.state_machine.predicates.project import is_any_sprint_ticketed
        assert is_any_sprint_ticketed(ctx) is True
        reader.any_sprint_in_phase.assert_called_once_with("ticketed")

    def test_false_when_no_sprint_ticketed(self):
        ctx = _project_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.project import is_any_sprint_ticketed
        assert is_any_sprint_ticketed(ctx) is False


class TestIsAnySprintExecuting:
    def test_true_when_sprint_executing(self):
        reader = _mock_reader()
        reader.any_sprint_in_phase.return_value = True
        ctx = _project_ctx(reader)
        from clasi.state_machine.predicates.project import is_any_sprint_executing
        assert is_any_sprint_executing(ctx) is True
        reader.any_sprint_in_phase.assert_called_once_with("executing")

    def test_false_when_no_sprint_executing(self):
        ctx = _project_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.project import is_any_sprint_executing
        assert is_any_sprint_executing(ctx) is False


# ---------------------------------------------------------------------------
# Sprint predicates (12 new + is_on_sprint_branch already tested above)
# ---------------------------------------------------------------------------


class TestIsSprintDocPresent:
    def test_true_when_file_exists(self):
        reader = _mock_reader(sprint_artifact_exists=True)
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_sprint_doc_present
        assert is_sprint_doc_present(ctx) is True

    def test_false_when_file_missing(self):
        ctx = _sprint_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.sprint import is_sprint_doc_present
        assert is_sprint_doc_present(ctx) is False

    def test_uses_sprint_id_and_artifact_name(self):
        reader = _mock_reader(sprint_artifact_exists=True)
        ctx = _sprint_ctx(sprint_id="007", reader=reader)
        from clasi.state_machine.predicates.sprint import is_sprint_doc_present
        is_sprint_doc_present(ctx)
        reader.sprint_artifact_exists.assert_called_once_with("007", "sprint.md")


class TestIsArchitecturePresent:
    def test_true_when_file_exists(self):
        reader = _mock_reader(sprint_artifact_exists=True)
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_architecture_present
        assert is_architecture_present(ctx) is True

    def test_false_when_file_missing(self):
        ctx = _sprint_ctx()
        from clasi.state_machine.predicates.sprint import is_architecture_present
        assert is_architecture_present(ctx) is False

    def test_uses_sprint_id_and_artifact_name(self):
        reader = _mock_reader(sprint_artifact_exists=True)
        ctx = _sprint_ctx(sprint_id="003", reader=reader)
        from clasi.state_machine.predicates.sprint import is_architecture_present
        is_architecture_present(ctx)
        reader.sprint_artifact_exists.assert_called_once_with(
            "003", "architecture-update.md"
        )


class TestIsUsecasesPresent:
    def test_true_when_file_exists(self):
        reader = _mock_reader(sprint_artifact_exists=True)
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_usecases_present
        assert is_usecases_present(ctx) is True

    def test_false_when_file_missing(self):
        ctx = _sprint_ctx()
        from clasi.state_machine.predicates.sprint import is_usecases_present
        assert is_usecases_present(ctx) is False

    def test_uses_usecases_md_not_hyphenated(self):
        reader = _mock_reader(sprint_artifact_exists=True)
        ctx = _sprint_ctx(sprint_id="005", reader=reader)
        from clasi.state_machine.predicates.sprint import is_usecases_present
        is_usecases_present(ctx)
        reader.sprint_artifact_exists.assert_called_once_with("005", "usecases.md")


class TestIsArchitectureReviewRecorded:
    def test_true_when_gate_present(self):
        reader = _mock_reader()
        reader.sprint_gate.return_value = {"result": "passed"}
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_architecture_review_recorded
        assert is_architecture_review_recorded(ctx) is True
        reader.sprint_gate.assert_called_once_with("005", "architecture_review")

    def test_false_when_gate_absent(self):
        ctx = _sprint_ctx()  # NullStateReader returns None
        from clasi.state_machine.predicates.sprint import is_architecture_review_recorded
        assert is_architecture_review_recorded(ctx) is False


class TestIsPreFlightSatisfied:
    def test_true_when_stakeholder_approval_gate_present(self):
        reader = _mock_reader()
        reader.sprint_gate.return_value = {"result": "approved"}
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_pre_flight_satisfied
        assert is_pre_flight_satisfied(ctx) is True

    def test_true_when_pre_flight_review_flag_is_skip(self):
        reader = _mock_reader()
        reader.sprint_gate.return_value = None  # no gate recorded
        reader.sprint_flag.return_value = "skip"
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_pre_flight_satisfied
        assert is_pre_flight_satisfied(ctx) is True

    def test_false_when_no_gate_and_no_skip_flag(self):
        ctx = _sprint_ctx()  # NullStateReader: no gate, flag returns ""
        from clasi.state_machine.predicates.sprint import is_pre_flight_satisfied
        assert is_pre_flight_satisfied(ctx) is False

    def test_false_when_flag_is_pause(self):
        reader = _mock_reader()
        reader.sprint_gate.return_value = None
        reader.sprint_flag.return_value = "pause"
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_pre_flight_satisfied
        assert is_pre_flight_satisfied(ctx) is False


class TestIsAtLeastOneTicket:
    def test_true_when_tickets_exist(self):
        reader = _mock_reader()
        reader.ticket_count.return_value = 3
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_at_least_one_ticket
        assert is_at_least_one_ticket(ctx) is True

    def test_false_when_no_tickets(self):
        ctx = _sprint_ctx()  # NullStateReader returns 0
        from clasi.state_machine.predicates.sprint import is_at_least_one_ticket
        assert is_at_least_one_ticket(ctx) is False

    def test_true_when_exactly_one_ticket(self):
        reader = _mock_reader()
        reader.ticket_count.return_value = 1
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_at_least_one_ticket
        assert is_at_least_one_ticket(ctx) is True


class TestIsNoOtherSprintExecuting:
    def test_true_when_no_lock_held(self):
        ctx = _sprint_ctx()  # NullStateReader returns None
        from clasi.state_machine.predicates.sprint import is_no_other_sprint_executing
        assert is_no_other_sprint_executing(ctx) is True

    def test_true_when_this_sprint_holds_lock(self):
        reader = _mock_reader()
        reader.execution_lock.return_value = {"sprint_id": "005"}
        ctx = _sprint_ctx(sprint_id="005", reader=reader)
        from clasi.state_machine.predicates.sprint import is_no_other_sprint_executing
        assert is_no_other_sprint_executing(ctx) is True

    def test_false_when_different_sprint_holds_lock(self):
        reader = _mock_reader()
        reader.execution_lock.return_value = {"sprint_id": "004"}
        ctx = _sprint_ctx(sprint_id="005", reader=reader)
        from clasi.state_machine.predicates.sprint import is_no_other_sprint_executing
        assert is_no_other_sprint_executing(ctx) is False


class TestIsExecutionLockHeldByThisSprint:
    def test_true_when_this_sprint_holds_lock(self):
        reader = _mock_reader()
        reader.execution_lock.return_value = {"sprint_id": "005"}
        ctx = _sprint_ctx(sprint_id="005", reader=reader)
        from clasi.state_machine.predicates.sprint import is_execution_lock_held_by_this_sprint
        assert is_execution_lock_held_by_this_sprint(ctx) is True

    def test_false_when_no_lock(self):
        ctx = _sprint_ctx()  # NullStateReader returns None
        from clasi.state_machine.predicates.sprint import is_execution_lock_held_by_this_sprint
        assert is_execution_lock_held_by_this_sprint(ctx) is False

    def test_false_when_different_sprint_holds_lock(self):
        reader = _mock_reader()
        reader.execution_lock.return_value = {"sprint_id": "004"}
        ctx = _sprint_ctx(sprint_id="005", reader=reader)
        from clasi.state_machine.predicates.sprint import is_execution_lock_held_by_this_sprint
        assert is_execution_lock_held_by_this_sprint(ctx) is False


class TestIsAllTicketsDone:
    def test_true_when_all_done(self):
        reader = _mock_reader()
        reader.all_tickets_done.return_value = True
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_all_tickets_done
        assert is_all_tickets_done(ctx) is True
        reader.all_tickets_done.assert_called_once_with("005")

    def test_false_when_not_all_done(self):
        ctx = _sprint_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.sprint import is_all_tickets_done
        assert is_all_tickets_done(ctx) is False


class TestIsReviewSatisfied:
    def test_true_when_sprint_review_gate_present(self):
        reader = _mock_reader()
        reader.sprint_gate.return_value = {"result": "passed"}
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_review_satisfied
        assert is_review_satisfied(ctx) is True

    def test_true_when_post_review_flag_is_skip(self):
        reader = _mock_reader()
        reader.sprint_gate.return_value = None
        reader.sprint_flag.return_value = "skip"
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_review_satisfied
        assert is_review_satisfied(ctx) is True

    def test_false_when_no_gate_and_no_skip_flag(self):
        ctx = _sprint_ctx()  # NullStateReader: no gate, flag returns ""
        from clasi.state_machine.predicates.sprint import is_review_satisfied
        assert is_review_satisfied(ctx) is False

    def test_false_when_flag_is_pause(self):
        reader = _mock_reader()
        reader.sprint_gate.return_value = None
        reader.sprint_flag.return_value = "pause"
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_review_satisfied
        assert is_review_satisfied(ctx) is False


class TestIsCloseReportPresent:
    def test_true_when_file_exists(self):
        reader = _mock_reader(sprint_artifact_exists=True)
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_close_report_present
        assert is_close_report_present(ctx) is True

    def test_false_when_file_missing(self):
        ctx = _sprint_ctx()
        from clasi.state_machine.predicates.sprint import is_close_report_present
        assert is_close_report_present(ctx) is False

    def test_uses_sprint_id_and_artifact_name(self):
        reader = _mock_reader(sprint_artifact_exists=True)
        ctx = _sprint_ctx(sprint_id="009", reader=reader)
        from clasi.state_machine.predicates.sprint import is_close_report_present
        is_close_report_present(ctx)
        reader.sprint_artifact_exists.assert_called_once_with(
            "009", "close-report.md"
        )


class TestIsBranchMerged:
    def test_true_when_branch_merged(self):
        reader = _mock_reader()
        reader.branch_merged.return_value = True
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_branch_merged
        assert is_branch_merged(ctx) is True
        reader.branch_merged.assert_called_once_with("005")

    def test_false_when_branch_not_merged(self):
        ctx = _sprint_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.sprint import is_branch_merged
        assert is_branch_merged(ctx) is False


# ---------------------------------------------------------------------------
# Ticket predicates (13)
# ---------------------------------------------------------------------------


class TestIsTicketFilePresent:
    def test_true_when_ticket_exists(self):
        reader = _mock_reader(ticket_file_present=True)
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_ticket_file_present
        assert is_ticket_file_present(ctx) is True

    def test_false_when_ticket_missing(self):
        reader = _mock_reader(ticket_file_present=False)
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_ticket_file_present
        assert is_ticket_file_present(ctx) is False

    def test_false_when_null_reader(self):
        ctx = _ticket_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.ticket import is_ticket_file_present
        assert is_ticket_file_present(ctx) is False


class TestIsTicketInDoneDir:
    def test_true_when_in_done_dir(self):
        reader = _mock_reader()
        reader.ticket_in_done_dir.return_value = True
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_ticket_in_done_dir
        assert is_ticket_in_done_dir(ctx) is True
        reader.ticket_in_done_dir.assert_called_once_with("005", "005-001")

    def test_false_when_not_in_done_dir(self):
        ctx = _ticket_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.ticket import is_ticket_in_done_dir
        assert is_ticket_in_done_dir(ctx) is False


class TestIsTicketNotInDoneDir:
    def test_true_when_not_in_done_dir(self):
        ctx = _ticket_ctx()  # NullStateReader returns False for ticket_in_done_dir
        from clasi.state_machine.predicates.ticket import is_ticket_not_in_done_dir
        assert is_ticket_not_in_done_dir(ctx) is True

    def test_false_when_in_done_dir(self):
        reader = _mock_reader()
        reader.ticket_in_done_dir.return_value = True
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_ticket_not_in_done_dir
        assert is_ticket_not_in_done_dir(ctx) is False


class TestIsNoExceptionBlock:
    def test_true_when_no_exception_block(self):
        ctx = _ticket_ctx()  # NullStateReader returns None
        from clasi.state_machine.predicates.ticket import is_no_exception_block
        assert is_no_exception_block(ctx) is True

    def test_false_when_exception_block_present(self):
        reader = _mock_reader()
        reader.exception_block.return_value = {
            "thrown_by": "programmer",
            "attempted": "...",
        }
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_no_exception_block
        assert is_no_exception_block(ctx) is False


class TestIsExceptionBlockPresent:
    def test_true_when_exception_block_present(self):
        reader = _mock_reader()
        reader.exception_block.return_value = {"thrown_by": "programmer"}
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_exception_block_present
        assert is_exception_block_present(ctx) is True
        reader.exception_block.assert_called_once_with("005", "005-001")

    def test_false_when_no_exception_block(self):
        ctx = _ticket_ctx()  # NullStateReader returns None
        from clasi.state_machine.predicates.ticket import is_exception_block_present
        assert is_exception_block_present(ctx) is False


class TestIsProgrammerDispatched:
    def test_true_when_dispatched(self):
        reader = _mock_reader()
        reader.programmer_dispatched.return_value = True
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_programmer_dispatched
        assert is_programmer_dispatched(ctx) is True
        reader.programmer_dispatched.assert_called_once_with("005", "005-001")

    def test_false_when_not_dispatched(self):
        ctx = _ticket_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.ticket import is_programmer_dispatched
        assert is_programmer_dispatched(ctx) is False


class TestIsSprintExecuting:
    def test_true_when_sprint_executing(self):
        reader = _mock_reader()
        reader.sprint_phase.return_value = "executing"
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_sprint_executing
        assert is_sprint_executing(ctx) is True
        reader.sprint_phase.assert_called_once_with("005")

    def test_false_when_sprint_not_executing(self):
        ctx = _ticket_ctx()  # NullStateReader returns ""
        from clasi.state_machine.predicates.ticket import is_sprint_executing
        assert is_sprint_executing(ctx) is False

    def test_false_when_sprint_in_review(self):
        reader = _mock_reader()
        reader.sprint_phase.return_value = "review"
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_sprint_executing
        assert is_sprint_executing(ctx) is False


class TestIsDependenciesDone:
    def test_true_when_all_dependencies_done(self):
        reader = _mock_reader()
        reader.dependencies_done.return_value = True
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_dependencies_done
        assert is_dependencies_done(ctx) is True
        reader.dependencies_done.assert_called_once_with("005", "005-001")

    def test_false_when_dependency_not_done(self):
        ctx = _ticket_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.ticket import is_dependencies_done
        assert is_dependencies_done(ctx) is False


class TestIsAcceptanceCriteriaMet:
    def test_true_when_all_criteria_checked(self):
        reader = _mock_reader()
        reader.acceptance_criteria_met.return_value = True
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_acceptance_criteria_met
        assert is_acceptance_criteria_met(ctx) is True
        reader.acceptance_criteria_met.assert_called_once_with("005", "005-001")

    def test_false_when_criteria_unchecked(self):
        ctx = _ticket_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.ticket import is_acceptance_criteria_met
        assert is_acceptance_criteria_met(ctx) is False


class TestIsTestsPassing:
    def test_true_when_tests_pass(self):
        reader = _mock_reader()
        reader.tests_passing.return_value = True
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_tests_passing
        assert is_tests_passing(ctx) is True
        reader.tests_passing.assert_called_once()

    def test_false_when_tests_fail(self):
        ctx = _ticket_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.ticket import is_tests_passing
        assert is_tests_passing(ctx) is False


class TestIsBlockerIdentified:
    def test_true_when_blocker_identified(self):
        reader = _mock_reader()
        reader.blocker_identified.return_value = True
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_blocker_identified
        assert is_blocker_identified(ctx) is True
        reader.blocker_identified.assert_called_once_with("005", "005-001")

    def test_false_when_no_blocker(self):
        ctx = _ticket_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.ticket import is_blocker_identified
        assert is_blocker_identified(ctx) is False


class TestIsBlockerResolved:
    def test_true_when_blocker_resolved(self):
        reader = _mock_reader()
        reader.blocker_resolved.return_value = True
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_blocker_resolved
        assert is_blocker_resolved(ctx) is True
        reader.blocker_resolved.assert_called_once_with("005", "005-001")

    def test_false_when_blocker_not_resolved(self):
        ctx = _ticket_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.ticket import is_blocker_resolved
        assert is_blocker_resolved(ctx) is False


class TestIsReopenRequested:
    def test_true_when_reopen_requested(self):
        reader = _mock_reader()
        reader.reopen_requested.return_value = True
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_reopen_requested
        assert is_reopen_requested(ctx) is True
        reader.reopen_requested.assert_called_once_with("005", "005-001")

    def test_false_when_no_reopen_requested(self):
        ctx = _ticket_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.ticket import is_reopen_requested
        assert is_reopen_requested(ctx) is False


# ---------------------------------------------------------------------------
# Integration: all predicates registered on package import
# ---------------------------------------------------------------------------


class TestPredicateRegistration:
    def test_all_project_predicates_registered(self):
        from clasi.state_machine.registry import list_predicates

        names = list_predicates()
        project_predicates = [
            "is_overview_absent",
            "is_overview_present",
            "is_on_default_branch",
            "is_on_sprint_branch",
            "is_execution_lock_held",
            "is_execution_lock_released",
            "is_any_sprint_ticketed",
            "is_any_sprint_executing",
        ]
        for name in project_predicates:
            assert name in names, f"Missing project predicate: {name}"

    def test_all_sprint_predicates_registered(self):
        from clasi.state_machine.registry import list_predicates

        names = list_predicates()
        sprint_predicates = [
            "is_sprint_doc_present",
            "is_architecture_present",
            "is_usecases_present",
            "is_architecture_review_recorded",
            "is_pre_flight_satisfied",
            "is_at_least_one_ticket",
            "is_no_other_sprint_executing",
            "is_execution_lock_held_by_this_sprint",
            "is_all_tickets_done",
            "is_review_satisfied",
            "is_close_report_present",
            "is_branch_merged",
        ]
        for name in sprint_predicates:
            assert name in names, f"Missing sprint predicate: {name}"

    def test_all_ticket_predicates_registered(self):
        from clasi.state_machine.registry import list_predicates

        names = list_predicates()
        ticket_predicates = [
            "is_ticket_file_present",
            "is_ticket_in_done_dir",
            "is_ticket_not_in_done_dir",
            "is_no_exception_block",
            "is_exception_block_present",
            "is_programmer_dispatched",
            "is_sprint_executing",
            "is_dependencies_done",
            "is_acceptance_criteria_met",
            "is_tests_passing",
            "is_blocker_identified",
            "is_blocker_resolved",
            "is_reopen_requested",
        ]
        for name in ticket_predicates:
            assert name in names, f"Missing ticket predicate: {name}"

    def test_total_predicate_count(self):
        """8 project + 12 sprint (shared is_on_sprint_branch) + 13 ticket = 33."""
        from clasi.state_machine.registry import list_predicates

        # is_on_sprint_branch is shared (registered once in project.py)
        # Project: 8, Sprint: 12 new (is_on_sprint_branch already counted), Ticket: 13
        # Total unique: 8 + 12 + 13 = 33
        names = list_predicates()
        assert len(names) == 33, (
            f"Expected 33 predicates, got {len(names)}: {names}"
        )
