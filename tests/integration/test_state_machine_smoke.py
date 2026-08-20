"""Integration smoke test for the CLASI state machine engine public API.

Exercises the full pipeline — import, load, context, evaluate, inspect —
without touching the real filesystem, git, or the database.

All three machine names are loaded to verify the YAML data files are
accessible via ``importlib.resources``.  Evaluation uses ``NullStateReader``
so every predicate returns False; ``evaluate_state`` is expected to raise
``NoMatchingStateError`` since no state's invariants are satisfied.
``inspect_transitions`` is called for the ``open`` state and returns a list
of ``TransitionResult`` objects whose ``name`` and ``to`` fields are populated.
"""

import pytest

import clasi.state_machine as sm
from clasi.state_machine import (
    AmbiguousStateError,
    DuplicatePredicateError,
    Machine,
    MachineSyntaxError,
    NoMatchingStateError,
    NullStateReader,
    ProjectContext,
    SprintContext,
    State,
    StateReader,
    StateMachineError,
    TicketContext,
    Transition,
    TransitionResult,
    UnknownPredicateError,
    evaluate_predicates,
    evaluate_state,
    get_predicate,
    inspect_transitions,
    list_predicates,
    load_machine,
)


# ---------------------------------------------------------------------------
# Predicate registration
# ---------------------------------------------------------------------------


def test_predicates_auto_registered() -> None:
    """Importing clasi.state_machine auto-registers all predicates."""
    predicates = list_predicates()
    assert len(predicates) >= 27, (
        f"Expected at least 27 predicates, got {len(predicates)}: {predicates}"
    )
    # A representative sample of well-known predicate names
    for name in (
        "is_any_sprint_ticketed",
        "is_on_sprint_branch",
        "is_ticket_in_done_dir",
    ):
        assert name in predicates, f"Expected predicate {name!r} in registry"


# ---------------------------------------------------------------------------
# __all__ completeness
# ---------------------------------------------------------------------------


def test_all_exports_importable() -> None:
    """Every name in __all__ is accessible as an attribute of the package."""
    for name in sm.__all__:
        assert hasattr(sm, name), f"{name!r} is in __all__ but not importable from clasi.state_machine"


# ---------------------------------------------------------------------------
# Machine loading
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("machine_name", ["project", "sprint", "ticket"])
def test_load_machine_returns_machine(machine_name: str) -> None:
    """load_machine succeeds for each of the three known machine names."""
    machine = load_machine(machine_name)
    assert isinstance(machine, Machine)
    assert machine.name == machine_name
    assert len(machine.states) > 0


# ---------------------------------------------------------------------------
# evaluate_state — NullStateReader returns False for everything
# ---------------------------------------------------------------------------


def test_evaluate_state_sprint_raises_no_match() -> None:
    """evaluate_state raises NoMatchingStateError when NullStateReader used.

    NullStateReader makes every predicate return False, so no state's
    invariants are satisfied, and NoMatchingStateError is expected.
    """
    machine = load_machine("sprint")
    reader = NullStateReader()
    project_ctx = ProjectContext(reader=reader)
    sprint_ctx = SprintContext(sprint_id="005", reader=reader, project=project_ctx)

    with pytest.raises(NoMatchingStateError):
        evaluate_state(machine, sprint_ctx)


def test_evaluate_state_ticket_raises_no_match() -> None:
    """evaluate_state raises NoMatchingStateError for ticket machine with NullStateReader."""
    machine = load_machine("ticket")
    reader = NullStateReader()
    project_ctx = ProjectContext(reader=reader)
    sprint_ctx = SprintContext(sprint_id="005", reader=reader, project=project_ctx)
    ticket_ctx = TicketContext(
        ticket_id="005-001",
        sprint_id="005",
        reader=reader,
        sprint=sprint_ctx,
    )

    with pytest.raises(NoMatchingStateError):
        evaluate_state(machine, ticket_ctx)


def test_evaluate_state_sprint_open_planned_ambiguity_resolves_determinately() -> None:
    """030/002 AC: the sprint machine's `open` and `planned` states share

    an identical invariant list (``[is_sprint_doc_present]``), so a
    context satisfying just that one predicate matches both states
    simultaneously. Confirm evaluate_state resolves this deterministically
    to the last-declared (more advanced) match -- "planned" -- instead of
    raising AmbiguousStateError.
    """

    class _SprintDocOnlyReader(NullStateReader):
        def sprint_artifact_exists(self, sprint_id: str, artifact_name: str) -> bool:
            return artifact_name == "sprint.md"

    machine = load_machine("sprint")
    reader = _SprintDocOnlyReader()
    project_ctx = ProjectContext(reader=reader)
    sprint_ctx = SprintContext(sprint_id="005", reader=reader, project=project_ctx)

    result = evaluate_state(machine, sprint_ctx)
    assert result.name == "planned"


# ---------------------------------------------------------------------------
# inspect_transitions — sprint machine "open" state
# ---------------------------------------------------------------------------


def test_inspect_transitions_sprint_open_returns_results() -> None:
    """inspect_transitions returns TransitionResult objects for the 'open' state."""
    machine = load_machine("sprint")
    reader = NullStateReader()
    project_ctx = ProjectContext(reader=reader)
    sprint_ctx = SprintContext(sprint_id="005", reader=reader, project=project_ctx)

    assert "open" in machine.states, "Expected 'open' state in sprint machine"

    results = inspect_transitions(machine, "open", sprint_ctx)

    assert isinstance(results, list)
    assert len(results) > 0

    for result in results:
        assert isinstance(result, TransitionResult)
        assert isinstance(result.name, str) and result.name
        assert isinstance(result.to, str) and result.to
        # With NullStateReader, no transitions should be fireable
        assert result.fireable is False
        assert len(result.blocked_by) > 0


# ---------------------------------------------------------------------------
# evaluate_predicates — diagnostic batch evaluation
# ---------------------------------------------------------------------------


def test_evaluate_predicates_returns_dict() -> None:
    """evaluate_predicates returns a bool/exception dict for each named predicate."""
    reader = NullStateReader()
    project_ctx = ProjectContext(reader=reader)

    result = evaluate_predicates(["is_any_sprint_ticketed", "is_any_sprint_executing"], project_ctx)

    assert isinstance(result, dict)
    assert set(result.keys()) == {"is_any_sprint_ticketed", "is_any_sprint_executing"}
    for val in result.values():
        assert val is False or isinstance(val, bool) or isinstance(val, Exception)


# ---------------------------------------------------------------------------
# StateReader protocol structural check
# ---------------------------------------------------------------------------


def test_null_state_reader_satisfies_protocol() -> None:
    """NullStateReader satisfies the StateReader Protocol (runtime_checkable)."""
    reader = NullStateReader()
    assert isinstance(reader, StateReader)
