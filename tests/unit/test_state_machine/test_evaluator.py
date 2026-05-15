"""Unit tests for clasi.state_machine.evaluator.

Covers all success paths and all error paths for:
- evaluate_state
- inspect_transitions
- evaluate_predicates
"""

from __future__ import annotations

import pytest

from clasi.state_machine.evaluator import (
    evaluate_predicates,
    evaluate_state,
    inspect_transitions,
)
from clasi.state_machine.models import (
    AmbiguousStateError,
    Machine,
    NoMatchingStateError,
    State,
    Transition,
    TransitionResult,
    UnknownPredicateError,
)
from clasi.state_machine.registry import clear_registry, predicate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    """Isolate registry state between tests."""
    clear_registry()
    yield
    clear_registry()


def _make_machine(states: dict[str, State], name: str = "test") -> Machine:
    """Build a minimal Machine for testing."""
    return Machine(name=name, context_type="object", initial=next(iter(states)), states=states)


def _simple_state(name: str, invariants: list[str] = None, transitions: dict = None) -> State:
    return State(
        name=name,
        description="",
        invariants=tuple(invariants or []),
        transitions=transitions or {},
    )


# ---------------------------------------------------------------------------
# evaluate_state — success paths
# ---------------------------------------------------------------------------


class TestEvaluateState:
    def test_single_match_returns_correct_state(self):
        @predicate("is_active")
        def is_active(ctx):
            return ctx == "active"

        @predicate("is_inactive")
        def is_inactive(ctx):
            return ctx == "inactive"

        machine = _make_machine(
            {
                "active": _simple_state("active", invariants=["is_active"]),
                "inactive": _simple_state("inactive", invariants=["is_inactive"]),
            }
        )

        result = evaluate_state(machine, "active")
        assert result.name == "active"

    def test_state_with_no_invariants_always_matches(self):
        """A state with an empty invariants list matches every context."""
        machine = _make_machine(
            {"open": _simple_state("open", invariants=[])}
        )
        result = evaluate_state(machine, object())
        assert result.name == "open"

    def test_multiple_invariants_all_must_pass(self):
        @predicate("pred_a")
        def pred_a(ctx):
            return ctx.get("a", False)

        @predicate("pred_b")
        def pred_b(ctx):
            return ctx.get("b", False)

        machine = _make_machine(
            {"matched": _simple_state("matched", invariants=["pred_a", "pred_b"])}
        )

        # Only a=True, b=False → no match for "matched"
        with pytest.raises(NoMatchingStateError):
            evaluate_state(machine, {"a": True, "b": False})

        # Both True → match
        result = evaluate_state(machine, {"a": True, "b": True})
        assert result.name == "matched"

    # --- error paths ---

    def test_no_match_raises_no_matching_state_error(self):
        @predicate("always_false")
        def always_false(ctx):
            return False

        machine = _make_machine(
            {"unreachable": _simple_state("unreachable", invariants=["always_false"])}
        )

        with pytest.raises(NoMatchingStateError):
            evaluate_state(machine, None)

    def test_ambiguous_raises_ambiguous_state_error(self):
        @predicate("always_true")
        def always_true(ctx):
            return True

        machine = _make_machine(
            {
                "state_a": _simple_state("state_a", invariants=["always_true"]),
                "state_b": _simple_state("state_b", invariants=["always_true"]),
            }
        )

        with pytest.raises(AmbiguousStateError):
            evaluate_state(machine, None)

    def test_ambiguous_error_contains_both_state_names(self):
        @predicate("always_true_2")
        def always_true_2(ctx):
            return True

        machine = _make_machine(
            {
                "alpha": _simple_state("alpha", invariants=["always_true_2"]),
                "beta": _simple_state("beta", invariants=["always_true_2"]),
            }
        )

        with pytest.raises(AmbiguousStateError) as exc_info:
            evaluate_state(machine, None)

        msg = str(exc_info.value)
        assert "alpha" in msg
        assert "beta" in msg

    def test_unknown_predicate_in_invariant_raises(self):
        machine = _make_machine(
            {"s": _simple_state("s", invariants=["not_registered"])}
        )
        with pytest.raises(UnknownPredicateError):
            evaluate_state(machine, None)


# ---------------------------------------------------------------------------
# inspect_transitions — success paths
# ---------------------------------------------------------------------------


class TestInspectTransitions:
    def _build_two_state_machine(self) -> Machine:
        """Helper: 'open' --(approve)--> 'closed'."""
        @predicate("is_ready")
        def is_ready(ctx):
            return ctx.get("ready", False)

        @predicate("is_closed")
        def is_closed(ctx):
            return ctx.get("closed", False)

        approve = Transition(name="approve", to="closed", conditions=["is_ready"])
        open_state = _simple_state("open", transitions={"approve": approve})
        closed_state = _simple_state("closed", invariants=["is_closed"])
        return _make_machine({"open": open_state, "closed": closed_state})

    def test_fireable_transition_returns_fireable_true(self):
        machine = self._build_two_state_machine()
        # "closed" invariant must also pass — so supply closed=True, ready=True
        results = inspect_transitions(machine, "open", {"ready": True, "closed": True})
        assert len(results) == 1
        assert results[0].fireable is True
        assert results[0].blocked_by == ()

    def test_non_fireable_transition_returns_fireable_false(self):
        machine = self._build_two_state_machine()
        results = inspect_transitions(machine, "open", {"ready": False, "closed": False})
        assert len(results) == 1
        assert results[0].fireable is False

    def test_blocked_by_contains_failing_condition(self):
        machine = self._build_two_state_machine()
        # ready=False so "is_ready" blocks; closed=True so dest invariant passes
        results = inspect_transitions(machine, "open", {"ready": False, "closed": True})
        assert "is_ready" in results[0].blocked_by

    def test_destination_invariant_in_blocked_by(self):
        machine = self._build_two_state_machine()
        # ready=True so condition passes; closed=False so destination invariant blocks
        results = inspect_transitions(machine, "open", {"ready": True, "closed": False})
        assert "is_closed" in results[0].blocked_by

    def test_both_condition_and_dest_invariant_failing_in_blocked_by(self):
        machine = self._build_two_state_machine()
        results = inspect_transitions(machine, "open", {"ready": False, "closed": False})
        blocked = results[0].blocked_by
        assert "is_ready" in blocked
        assert "is_closed" in blocked

    def test_transition_name_and_to_are_correct(self):
        machine = self._build_two_state_machine()
        results = inspect_transitions(machine, "open", {})
        assert results[0].name == "approve"
        assert results[0].to == "closed"

    def test_state_with_no_transitions_returns_empty_list(self):
        machine = self._build_two_state_machine()
        results = inspect_transitions(machine, "closed", {})
        assert results == []

    def test_returns_transition_result_instances(self):
        machine = self._build_two_state_machine()
        results = inspect_transitions(machine, "open", {})
        assert all(isinstance(r, TransitionResult) for r in results)

    def test_unconditional_transition_is_always_fireable(self):
        """A transition with no conditions and a dest state with no invariants fires freely."""
        go = Transition(name="go", to="done", conditions=[])
        start = _simple_state("start", transitions={"go": go})
        done = _simple_state("done", invariants=[])
        machine = _make_machine({"start": start, "done": done})
        results = inspect_transitions(machine, "start", None)
        assert results[0].fireable is True
        assert results[0].blocked_by == ()

    # --- error paths ---

    def test_unknown_state_name_raises_key_error(self):
        machine = _make_machine({"only": _simple_state("only")})
        with pytest.raises(KeyError):
            inspect_transitions(machine, "nonexistent", None)

    def test_unknown_predicate_in_condition_raises(self):
        bad_trans = Transition(name="t", to="b", conditions=["not_registered"])
        a = _simple_state("a", transitions={"t": bad_trans})
        b = _simple_state("b")
        machine = _make_machine({"a": a, "b": b})
        with pytest.raises(UnknownPredicateError):
            inspect_transitions(machine, "a", None)

    def test_multiple_transitions_all_evaluated(self):
        @predicate("is_p")
        def is_p(ctx):
            return True

        @predicate("is_q")
        def is_q(ctx):
            return False

        t1 = Transition(name="t1", to="b", conditions=["is_p"])
        t2 = Transition(name="t2", to="c", conditions=["is_q"])
        a = _simple_state("a", transitions={"t1": t1, "t2": t2})
        b = _simple_state("b")
        c = _simple_state("c")
        machine = _make_machine({"a": a, "b": b, "c": c})
        results = inspect_transitions(machine, "a", None)
        assert len(results) == 2
        by_name = {r.name: r for r in results}
        assert by_name["t1"].fireable is True
        assert by_name["t2"].fireable is False


# ---------------------------------------------------------------------------
# evaluate_predicates — success paths
# ---------------------------------------------------------------------------


class TestEvaluatePredicates:
    def test_all_passing_returns_all_true(self):
        @predicate("ep_a")
        def ep_a(ctx):
            return True

        @predicate("ep_b")
        def ep_b(ctx):
            return True

        result = evaluate_predicates(["ep_a", "ep_b"], None)
        assert result == {"ep_a": True, "ep_b": True}

    def test_failing_predicate_returns_false(self):
        @predicate("ep_false")
        def ep_false(ctx):
            return False

        result = evaluate_predicates(["ep_false"], None)
        assert result == {"ep_false": False}

    def test_exception_captured_not_propagated(self):
        @predicate("ep_raises")
        def ep_raises(ctx):
            raise ValueError("boom")

        result = evaluate_predicates(["ep_raises"], None)
        assert isinstance(result["ep_raises"], ValueError)
        assert "boom" in str(result["ep_raises"])

    def test_exception_does_not_abort_remaining_predicates(self):
        @predicate("ep_err")
        def ep_err(ctx):
            raise RuntimeError("fail")

        @predicate("ep_ok")
        def ep_ok(ctx):
            return True

        result = evaluate_predicates(["ep_err", "ep_ok"], None)
        assert isinstance(result["ep_err"], RuntimeError)
        assert result["ep_ok"] is True

    def test_empty_names_list_returns_empty_dict(self):
        result = evaluate_predicates([], None)
        assert result == {}

    def test_context_passed_to_predicate(self):
        @predicate("ep_ctx")
        def ep_ctx(ctx):
            return ctx == "expected"

        result = evaluate_predicates(["ep_ctx"], "expected")
        assert result["ep_ctx"] is True

        result2 = evaluate_predicates(["ep_ctx"], "wrong")
        assert result2["ep_ctx"] is False

    # --- error paths ---

    def test_unknown_predicate_raises_before_calling_any(self):
        call_log = []

        @predicate("ep_good")
        def ep_good(ctx):
            call_log.append("called")
            return True

        # "ep_missing" is not registered — should fast-fail before calling ep_good
        with pytest.raises(UnknownPredicateError):
            evaluate_predicates(["ep_missing", "ep_good"], None)

        assert call_log == [], "No predicate should be called after fast-fail"

    def test_unknown_predicate_error_contains_name(self):
        with pytest.raises(UnknownPredicateError) as exc_info:
            evaluate_predicates(["no_such_pred"], None)

        assert "no_such_pred" in str(exc_info.value)
