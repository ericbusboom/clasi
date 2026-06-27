"""Public API for the CLASI state machine engine.

This module re-exports the complete set of symbols that sprint 006
(the ``clasi-status`` command) will consume.  Importing this package
also triggers registration of all ``is_*`` predicates via the
``clasi.state_machine.predicates`` sub-package side-effect import.

Typical sprint-006 usage pattern::

    from clasi.state_machine import (
        load_machine,
        evaluate_state,
        inspect_transitions,
        SprintContext,
        NoMatchingStateError,
    )

    machine = load_machine("sprint")
    ctx = SprintContext(sprint_id="005", reader=my_reader, project=proj_ctx)
    try:
        state = evaluate_state(machine, ctx)
    except NoMatchingStateError:
        ...  # sprint not yet in a recognized state

Sprint 006 must supply a ``StateReaderImpl`` (wired to the real
filesystem / git / StateDB) to get meaningful results from
``evaluate_state``.  Sprint 005 tests use ``NullStateReader`` so no
real I/O is required.
"""

from clasi.state_machine.models import (
    AmbiguousStateError,
    DuplicatePredicateError,
    Machine,
    MachineSyntaxError,
    NoMatchingStateError,
    State,
    StateMachineError,
    Transition,
    TransitionResult,
    UnknownPredicateError,
)
from clasi.state_machine.loader import load_machine
from clasi.state_machine.registry import get_predicate, list_predicates
from clasi.state_machine.evaluator import (
    evaluate_state,
    inspect_transitions,
    evaluate_predicates,
)
from clasi.state_machine.context import (
    NullStateReader,
    ProjectContext,
    SprintContext,
    StateReader,
    TicketContext,
)
import clasi.state_machine.predicates  # noqa: F401 — side-effect: registers all predicates

__all__ = [
    # Loader
    "load_machine",
    # Evaluator
    "evaluate_state",
    "inspect_transitions",
    "evaluate_predicates",
    # Registry
    "get_predicate",
    "list_predicates",
    # Context
    "ProjectContext",
    "SprintContext",
    "TicketContext",
    "StateReader",
    "NullStateReader",
    # Models
    "Machine",
    "State",
    "Transition",
    "TransitionResult",
    # Exceptions
    "StateMachineError",
    "MachineSyntaxError",
    "DuplicatePredicateError",
    "UnknownPredicateError",
    "NoMatchingStateError",
    "AmbiguousStateError",
]
