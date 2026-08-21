"""Unit tests for clasi.state_machine.predicates.

Covers True and False cases for all 27 unique predicates:
- 8 project predicates (includes is_on_sprint_branch)
- 8 sprint-only predicates (is_on_sprint_branch shared with project)
- 11 ticket predicates

Uses ``unittest.mock.MagicMock`` or stub readers to keep tests isolated
from the filesystem, git, and the database.

Registry isolation between tests (and between this module and whatever
runs after it in the same pytest process) is provided by the autouse
``_clean_registry`` fixture in this package's ``conftest.py`` — see that
file's docstring for why it's a snapshot/restore fixture rather than a
plain clear. This module additionally needs the *real* predicates
registered for its own test bodies to exercise, which ``_clean_registry``
alone doesn't provide (it only guarantees an empty, private registry);
the ``_real_predicates`` fixture below layers that on top by reloading
the real predicate modules after ``_clean_registry`` has cleared the
registry for this test.
"""

from __future__ import annotations

import importlib
import pytest
from unittest.mock import MagicMock

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
def _real_predicates(_clean_registry):
    """Populate the registry with the real predicate modules for this test.

    ``_clean_registry`` (autouse, from this package's ``conftest.py``) has
    already snapshotted and cleared the registry for this test's isolation
    by the time this fixture's setup runs — depending on it by name is
    what guarantees that ordering. This fixture reloads the real predicate
    modules on top of that clean slate so this module's tests exercise
    production predicates.

    ``@predicate`` decorators run at import time.  Since Python caches
    modules after the first import, we must explicitly reload each module
    to re-trigger registration after ``_clean_registry`` clears the
    registry.  Import order matters: ``project`` must be reloaded before
    ``sprint`` because ``sprint`` depends on ``is_on_sprint_branch``
    already being registered.

    No teardown needed here: ``_clean_registry``'s teardown (which runs
    after this fixture's, since it was set up first) clears the registry
    and restores the pre-test snapshot regardless of what got registered
    during the test.
    """
    importlib.reload(clasi.state_machine.predicates.project)
    importlib.reload(clasi.state_machine.predicates.sprint)
    importlib.reload(clasi.state_machine.predicates.ticket)


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
        # "ticketing" is the DB phase vocabulary's real name for this stage
        # (schemas/se-process/schema.yaml) -- there is no "ticketed" phase.
        reader.any_sprint_in_phase.assert_called_once_with("ticketing")

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


class TestIsArchitectureReviewRecorded:
    def test_true_when_gate_result_is_passed(self):
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

    def test_true_when_gate_result_is_skipped(self):
        """A 'skipped' architecture_review gate record satisfies this

        predicate, matching StateDB.advance_phase's own
        `result in {"passed", "skipped"}` semantics.
        """
        reader = _mock_reader()
        reader.sprint_gate.return_value = {"result": "skipped"}
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_architecture_review_recorded
        assert is_architecture_review_recorded(ctx) is True

    def test_false_when_gate_result_is_failed(self):
        """A FAILED gate record must NOT satisfy this predicate.

        Regression test: the predicate used to check `is not None` only,
        so a failed review satisfied it just like a passed one.
        """
        reader = _mock_reader()
        reader.sprint_gate.return_value = {"result": "failed"}
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_architecture_review_recorded
        assert is_architecture_review_recorded(ctx) is False


class TestIsPreFlightSatisfied:
    def test_true_when_stakeholder_approval_gate_result_is_passed(self):
        reader = _mock_reader()
        reader.sprint_gate.return_value = {"result": "passed"}
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_pre_flight_satisfied
        assert is_pre_flight_satisfied(ctx) is True

    def test_true_when_stakeholder_approval_gate_result_is_skipped(self):
        reader = _mock_reader()
        reader.sprint_gate.return_value = {"result": "skipped"}
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_pre_flight_satisfied
        assert is_pre_flight_satisfied(ctx) is True

    def test_false_when_gate_result_is_failed(self):
        """A FAILED gate record must NOT satisfy this predicate.

        Regression test: the predicate used to check `is not None` only,
        so a failed review satisfied it just like a passed one.
        """
        reader = _mock_reader()
        reader.sprint_gate.return_value = {"result": "failed"}
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_pre_flight_satisfied
        assert is_pre_flight_satisfied(ctx) is False

    def test_false_when_no_gate(self):
        ctx = _sprint_ctx()  # NullStateReader: no gate recorded
        from clasi.state_machine.predicates.sprint import is_pre_flight_satisfied
        assert is_pre_flight_satisfied(ctx) is False

    def test_pre_flight_review_flag_no_longer_consulted(self):
        """The `pre_flight_review` frontmatter flag has zero writers, so

        the predicate no longer falls back to it -- only the
        stakeholder_approval gate result matters, regardless of what the
        flag is set to.
        """
        reader = _mock_reader()
        reader.sprint_gate.return_value = None
        reader.sprint_flag.return_value = "skip"
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_pre_flight_satisfied
        assert is_pre_flight_satisfied(ctx) is False
        reader.sprint_flag.assert_not_called()


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


class TestIsSprintArchived:
    """031/001: the sole invariant of the `closed` state -- a cheap,
    git-free directory-location check. A prior merged-branch invariant
    was removed because `close_sprint` deletes the sprint branch after
    merging it by default, which made that invariant permanently
    unsatisfiable for a correctly closed sprint."""

    def test_true_when_archived(self):
        reader = _mock_reader()
        reader.sprint_is_archived.return_value = True
        ctx = _sprint_ctx(reader=reader)
        from clasi.state_machine.predicates.sprint import is_sprint_archived
        assert is_sprint_archived(ctx) is True
        reader.sprint_is_archived.assert_called_once_with("005")

    def test_false_when_not_archived(self):
        ctx = _sprint_ctx()  # NullStateReader returns False
        from clasi.state_machine.predicates.sprint import is_sprint_archived
        assert is_sprint_archived(ctx) is False


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


# ---------------------------------------------------------------------------
# Phase-string agreement (030/002 regression class)
# ---------------------------------------------------------------------------
#
# `is_any_sprint_ticketed` queried DB phase "ticketed" -- a string that
# never existed in the DB phase vocabulary (only "ticketing" does,
# per `schemas/se-process/schema.yaml`) -- which permanently blocked the
# project machine's `enter-sprint` transition. None of the per-predicate
# unit tests above caught it, because they stub the reader to *echo back*
# whatever phase string the predicate under test happens to pass in
# (`reader.any_sprint_in_phase.return_value = True` unconditionally) --
# which "agrees" with any string, correct or not.
#
# These tests instead check each phase-referencing predicate's real
# behavior against every phase in ArtifactGraph.phases() -- the actual DB
# phase vocabulary -- so a typo'd or renamed phase string fails loudly
# regardless of what a hand-stubbed reader is told to return.


class TestPhaseStringAgreement:
    def _artifact_graph_phases(self) -> list[str]:
        from clasi.state_db_class import PHASES
        return PHASES

    def test_artifact_graph_phases_sanity(self):
        """Guard the guard: confirm the real phase vocabulary is what this

        test class assumes, so a schema.yaml change doesn't silently make
        the tests below vacuous.
        """
        phases = self._artifact_graph_phases()
        assert "ticketing" in phases
        assert "executing" in phases
        assert "ticketed" not in phases

    def test_is_any_sprint_ticketed_call_argument_is_a_real_phase(self):
        """Captures the literal phase string is_any_sprint_ticketed passes

        to `any_sprint_in_phase` and checks it against the real phase
        vocabulary -- independent of what the mock is told to return.
        """
        reader = _mock_reader()
        ctx = _project_ctx(reader)
        from clasi.state_machine.predicates.project import is_any_sprint_ticketed
        is_any_sprint_ticketed(ctx)
        reader.any_sprint_in_phase.assert_called_once()
        queried_phase = reader.any_sprint_in_phase.call_args.args[0]
        assert queried_phase in self._artifact_graph_phases(), (
            f"is_any_sprint_ticketed queried phase {queried_phase!r}, which "
            f"does not exist in ArtifactGraph.phases(): "
            f"{self._artifact_graph_phases()}"
        )
        assert queried_phase == "ticketing"

    def test_is_any_sprint_executing_call_argument_is_a_real_phase(self):
        reader = _mock_reader()
        ctx = _project_ctx(reader)
        from clasi.state_machine.predicates.project import is_any_sprint_executing
        is_any_sprint_executing(ctx)
        reader.any_sprint_in_phase.assert_called_once()
        queried_phase = reader.any_sprint_in_phase.call_args.args[0]
        assert queried_phase in self._artifact_graph_phases(), (
            f"is_any_sprint_executing queried phase {queried_phase!r}, which "
            f"does not exist in ArtifactGraph.phases(): "
            f"{self._artifact_graph_phases()}"
        )
        assert queried_phase == "executing"

    def test_is_any_sprint_ticketed_matches_exactly_one_real_phase(self):
        """Behavioral cross-check: feed every real phase through the

        reader, one at a time, and confirm the predicate is satisfied by
        exactly the phase it is documented to mean. If the predicate's
        hardcoded query string were invalid (e.g. "ticketed"), no real
        phase would ever satisfy it and `matched` would be empty.
        """
        from clasi.state_machine.predicates.project import is_any_sprint_ticketed

        matched = []
        for phase in self._artifact_graph_phases():
            reader = MagicMock()
            reader.any_sprint_in_phase.side_effect = lambda p, _phase=phase: p == _phase
            ctx = _project_ctx(reader)
            if is_any_sprint_ticketed(ctx):
                matched.append(phase)
        assert matched == ["ticketing"], (
            f"is_any_sprint_ticketed should be satisfiable by exactly the "
            f"real 'ticketing' phase; matched {matched!r} instead"
        )

    def test_is_any_sprint_executing_matches_exactly_one_real_phase(self):
        from clasi.state_machine.predicates.project import is_any_sprint_executing

        matched = []
        for phase in self._artifact_graph_phases():
            reader = MagicMock()
            reader.any_sprint_in_phase.side_effect = lambda p, _phase=phase: p == _phase
            ctx = _project_ctx(reader)
            if is_any_sprint_executing(ctx):
                matched.append(phase)
        assert matched == ["executing"], (
            f"is_any_sprint_executing should be satisfiable by exactly the "
            f"real 'executing' phase; matched {matched!r} instead"
        )

    def test_is_sprint_executing_ticket_predicate_matches_exactly_one_real_phase(self):
        """`is_sprint_executing` (ticket machine) compares

        `reader.sprint_phase(...)` against a hardcoded literal rather than
        passing a phase string as a call argument, so its phase string
        can't be captured via call_args -- this behavioral cross-check
        covers it the same way as the call-argument predicates above.
        """
        from clasi.state_machine.predicates.ticket import is_sprint_executing

        matched = []
        for phase in self._artifact_graph_phases():
            reader = _mock_reader()
            reader.sprint_phase.return_value = phase
            ctx = _ticket_ctx(reader=reader)
            if is_sprint_executing(ctx):
                matched.append(phase)
        assert matched == ["executing"], (
            f"is_sprint_executing should be satisfiable by exactly the "
            f"real 'executing' phase; matched {matched!r} instead"
        )


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
            "is_architecture_review_recorded",
            "is_pre_flight_satisfied",
            "is_at_least_one_ticket",
            "is_no_other_sprint_executing",
            "is_execution_lock_held_by_this_sprint",
            "is_all_tickets_done",
            "is_sprint_archived",
        ]
        for name in sprint_predicates:
            assert name in names, f"Missing sprint predicate: {name}"

    def test_is_architecture_present_and_is_usecases_present_not_registered(self):
        """Single-doc model: these two predicates were removed entirely —

        use cases and architecture are sections of sprint.md, not
        separate files whose presence can be checked.
        """
        from clasi.state_machine.registry import list_predicates

        names = list_predicates()
        assert "is_architecture_present" not in names
        assert "is_usecases_present" not in names

    def test_unsatisfiable_predicates_removed_not_registered(self):
        """030/002: these predicates referenced gates/flags/markers the

        shipped toolchain never writes (`sprint_review` gate rejected by
        `record_gate`'s VALID_GATE_NAMES; the `pre_flight_review`/
        `post_review` frontmatter flags; the `.clasi/test-cache` marker;
        the `reopen_requested` MCP call). They were removed rather than
        made recordable.
        """
        from clasi.state_machine.registry import list_predicates

        names = list_predicates()
        for removed in (
            "is_review_satisfied",
            "is_close_report_present",
            "is_tests_passing",
            "is_reopen_requested",
        ):
            assert removed not in names, f"{removed} should have been removed"

    def test_merged_branch_predicate_removed_not_registered(self):
        """031/001: a distinct category from the 030/002 predicates above --

        this predicate's backing signal *did* have a writer (a real git
        query), but the toolchain destroyed that signal by design:
        `close_sprint` deletes the sprint branch after merging it, so the
        predicate could never be satisfied for a correctly closed sprint.
        Removed rather than special-cased.
        """
        from clasi.state_machine.registry import list_predicates

        names = list_predicates()
        assert "is_branch_merged" not in names

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
            "is_blocker_identified",
            "is_blocker_resolved",
        ]
        for name in ticket_predicates:
            assert name in names, f"Missing ticket predicate: {name}"

    def test_total_predicate_count(self):
        """8 project + 8 sprint (shared is_on_sprint_branch) + 11 ticket = 27."""
        from clasi.state_machine.registry import list_predicates

        # is_on_sprint_branch is shared (registered once in project.py)
        # Project: 8, Sprint: 8 (is_architecture_present/is_usecases_present,
        # is_review_satisfied, is_close_report_present removed;
        # is_on_sprint_branch already counted; is_sprint_archived added by
        # 030/002's regression fix; the merged-branch predicate removed by
        # 031/001), Ticket: 11
        # (is_tests_passing, is_reopen_requested removed)
        # Total unique: 8 + 8 + 11 = 27
        names = list_predicates()
        assert len(names) == 27, (
            f"Expected 27 predicates, got {len(names)}: {names}"
        )
