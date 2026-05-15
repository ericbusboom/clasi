"""State evaluator for the CLASI state machine engine.

This module provides three public functions that form the computational core
of the state machine subsystem:

- :func:`evaluate_state` — determine which state a context is currently in.
- :func:`inspect_transitions` — enumerate outbound transitions from a given
  state and report which are fireable and what is blocking the rest.
- :func:`evaluate_predicates` — evaluate a list of predicates and return a
  result dict, capturing per-predicate exceptions rather than propagating them.

Design rule: "conditions + destination invariants"
--------------------------------------------------
When inspecting a transition, the engine automatically appends the
destination state's invariants to the transition's ``conditions`` list as
additional guards.  A transition is only fireable when *both* the explicit
conditions *and* the destination invariants are satisfied.  This rule is
documented in ``docs/design/state-machines.md`` and enforced here in
:func:`inspect_transitions`.
"""

from __future__ import annotations

from clasi.state_machine.models import (
    AmbiguousStateError,
    Machine,
    NoMatchingStateError,
    State,
    TransitionResult,
    UnknownPredicateError,
)
from clasi.state_machine.registry import get_predicate


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_state(machine: Machine, context: object) -> State:
    """Return the single state whose invariants are all satisfied by *context*.

    Iterates every state in *machine*, evaluates each state's invariant
    predicates against *context*, and returns the unique match.

    Args:
        machine: The :class:`~clasi.state_machine.models.Machine` to evaluate.
        context: A context object compatible with the predicates registered
            for this machine (e.g. :class:`~clasi.state_machine.context.TicketContext`).

    Returns:
        The :class:`~clasi.state_machine.models.State` whose invariants all
        return ``True`` for *context*.

    Raises:
        NoMatchingStateError: If no state's invariants are all satisfied.
        AmbiguousStateError: If more than one state's invariants are all
            satisfied simultaneously (includes both matching state names in
            the error message).
        UnknownPredicateError: If any invariant predicate name is not
            registered in the global registry.
    """
    matches: list[State] = []

    for state in machine.states.values():
        if all(get_predicate(inv)(context) for inv in state.invariants):
            matches.append(state)

    if len(matches) == 0:
        raise NoMatchingStateError(
            f"No state in machine {machine.name!r} matches the current context. "
            f"States checked: {list(machine.states.keys())}"
        )
    if len(matches) > 1:
        matching_names = [s.name for s in matches]
        raise AmbiguousStateError(
            f"Multiple states in machine {machine.name!r} match the current "
            f"context simultaneously: {matching_names}. "
            "State invariants must be mutually exclusive."
        )

    return matches[0]


def inspect_transitions(
    machine: Machine, state_name: str, context: object
) -> list[TransitionResult]:
    """Return one :class:`~clasi.state_machine.models.TransitionResult` per
    outbound transition from *state_name*.

    For each transition the engine evaluates:

    1. The transition's own ``conditions`` predicates.
    2. The destination state's ``invariants`` predicates (added automatically).

    A transition is **fireable** when every predicate in both sets returns
    ``True``.  The ``blocked_by`` list names every predicate that returned
    ``False`` (conditions and destination invariants combined).

    Args:
        machine: The :class:`~clasi.state_machine.models.Machine` containing
            *state_name*.
        state_name: Name of the current state.  Must be a key in
            ``machine.states``.
        context: A context object compatible with the predicates registered
            for this machine.

    Returns:
        A list of :class:`~clasi.state_machine.models.TransitionResult`
        objects, one per outbound transition, in the iteration order of the
        state's ``transitions`` dict.

    Raises:
        KeyError: If *state_name* is not present in ``machine.states``.
        UnknownPredicateError: If any predicate name referenced by a
            transition or destination invariant is not registered.
    """
    state = machine.states[state_name]  # raises KeyError if absent

    results: list[TransitionResult] = []

    for transition in state.transitions.values():
        # Combine the transition's own conditions with the destination
        # state's invariants (the "conditions + destination invariants" rule).
        dest_state = machine.states.get(transition.to)
        dest_invariants: tuple[str, ...] = (
            dest_state.invariants if dest_state is not None else ()
        )
        all_predicates = list(transition.conditions) + list(dest_invariants)

        blocked_by: list[str] = []
        for pred_name in all_predicates:
            fn = get_predicate(pred_name)  # raises UnknownPredicateError if missing
            if not fn(context):
                blocked_by.append(pred_name)

        fireable = len(blocked_by) == 0
        results.append(
            TransitionResult(
                name=transition.name,
                to=transition.to,
                fireable=fireable,
                blocked_by=tuple(blocked_by),
            )
        )

    return results


def evaluate_predicates(
    names: list[str], context: object
) -> dict[str, bool | Exception]:
    """Evaluate each named predicate against *context* and return a result dict.

    This function is designed for **diagnostic / status-reporting** use cases
    where a caller wants to see the outcome of every predicate in one pass
    without a single failure aborting the whole evaluation.

    Per-predicate exceptions are **captured** into the dict rather than
    propagated.  The caller can inspect the dict to see which predicates
    raised and why.

    Args:
        names: List of predicate names to evaluate.  All names are validated
            against the registry **before** any predicate is called — an
            unknown name raises :class:`~clasi.state_machine.models.UnknownPredicateError`
            immediately (fast-fail).
        context: A context object passed to each predicate.

    Returns:
        A dict mapping each name in *names* to either:

        - ``True`` / ``False`` — the boolean result of the predicate, or
        - an :class:`Exception` instance — if the predicate raised during
          evaluation.

    Raises:
        UnknownPredicateError: If any name in *names* is not registered.
            Raised before calling any predicate (fast-fail).
    """
    # Fast-fail: validate all names before calling any predicate.
    fns: dict[str, object] = {}
    for name in names:
        fns[name] = get_predicate(name)  # raises UnknownPredicateError if missing

    results: dict[str, bool | Exception] = {}
    for name, fn in fns.items():
        try:
            results[name] = bool(fn(context))  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001
            results[name] = exc

    return results
