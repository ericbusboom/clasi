"""In-memory data model for the CLASI state machine engine.

Pure dataclasses and exceptions — no I/O, no registry, no evaluation logic.
Every other module in the subsystem imports from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class StateMachineError(Exception):
    """Base class for all state machine errors."""


class MachineSyntaxError(StateMachineError):
    """Raised when a machine definition is structurally invalid."""


class DuplicatePredicateError(StateMachineError):
    """Raised when a predicate name is registered more than once."""


class UnknownPredicateError(StateMachineError):
    """Raised when a transition references a predicate that is not registered."""


class NoMatchingStateError(StateMachineError):
    """Raised when no state's invariants are satisfied by the current context."""


class AmbiguousStateError(StateMachineError):
    """Raised when more than one state's invariants are satisfied simultaneously."""


# ---------------------------------------------------------------------------
# Core dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Transition:
    """A directed edge in the state machine graph.

    Attributes:
        name: Logical name of the transition (e.g. ``"approve"``).
        to: Name of the target state.
        conditions: List of predicate names that must all be true for the
            transition to fire.  Empty list means unconditionally fireable.
        action: Optional name of a side-effect action to invoke when the
            transition fires.  ``None`` means no action.
    """

    name: str
    to: str
    conditions: tuple[str, ...] = field(default_factory=tuple)
    action: str | None = None

    def __post_init__(self) -> None:
        # Normalise: accept a list at construction but store as tuple so the
        # dataclass remains hashable despite frozen=True.
        if isinstance(self.conditions, list):
            object.__setattr__(self, "conditions", tuple(self.conditions))


@dataclass(frozen=True)
class State:
    """A node in the state machine graph.

    Attributes:
        name: Unique name within the machine (e.g. ``"planning"``).
        description: Human-readable description.
        invariants: Predicate names that must *all* be true for this state to
            be considered active.  Used by ``evaluate_state``.
        transitions: Mapping from transition name to ``Transition`` object.
    """

    name: str
    description: str = ""
    invariants: tuple[str, ...] = field(default_factory=tuple)
    transitions: dict[str, Transition] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.invariants, list):
            object.__setattr__(self, "invariants", tuple(self.invariants))
        # Ensure transitions is a plain dict (copy to prevent shared mutable state).
        object.__setattr__(self, "transitions", dict(self.transitions))


@dataclass(frozen=True)
class Machine:
    """Complete description of a state machine.

    Attributes:
        name: Machine identifier (e.g. ``"ticket"``).
        context_type: Dotted Python class name of the context object
            expected by predicates (e.g. ``"clasi.state_machine.context.TicketContext"``).
        initial: Name of the initial state.
        states: Mapping from state name to ``State`` object.
    """

    name: str
    context_type: str
    initial: str
    states: dict[str, State] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "states", dict(self.states))

    def terminal_states(self) -> tuple[str, ...]:
        """Return the names of states with no outbound transitions.

        A terminal state is one nothing can leave — there is no next
        action to unblock and no reconciliation to perform once an
        artifact is declared to be in it. Derived structurally from the
        loaded machine (rather than any hardcoded state name) so a
        renamed or added terminal state is picked up automatically.
        """
        return tuple(
            name for name, state in self.states.items() if not state.transitions
        )


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransitionResult:
    """The evaluated result for a single transition.

    Attributes:
        name: Name of the transition.
        to: Name of the target state.
        fireable: ``True`` if all conditions are currently satisfied.
        blocked_by: Predicate names whose evaluation returned ``False``.
            Empty when ``fireable`` is ``True``.
    """

    name: str
    to: str
    fireable: bool
    blocked_by: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if isinstance(self.blocked_by, list):
            object.__setattr__(self, "blocked_by", tuple(self.blocked_by))
