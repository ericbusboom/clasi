"""Unit tests for clasi.state_machine.models.

Verifies construction, field access, immutability, and exception hierarchy.
"""

from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError

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


# ---------------------------------------------------------------------------
# Transition
# ---------------------------------------------------------------------------


class TestTransition:
    def test_basic_construction(self):
        t = Transition(name="approve", to="active")
        assert t.name == "approve"
        assert t.to == "active"
        assert t.conditions == ()
        assert t.action is None

    def test_with_conditions_and_action(self):
        t = Transition(
            name="start",
            to="executing",
            conditions=["is_ready", "has_tickets"],
            action="notify",
        )
        assert t.conditions == ("is_ready", "has_tickets")
        assert t.action == "notify"

    def test_list_conditions_normalised_to_tuple(self):
        t = Transition(name="x", to="y", conditions=["a", "b"])
        assert isinstance(t.conditions, tuple)

    def test_tuple_conditions_accepted(self):
        t = Transition(name="x", to="y", conditions=("a", "b"))
        assert t.conditions == ("a", "b")

    def test_immutable(self):
        t = Transition(name="approve", to="active")
        with pytest.raises(FrozenInstanceError):
            t.name = "other"  # type: ignore[misc]

    def test_hashable(self):
        t = Transition(name="x", to="y")
        assert hash(t) is not None
        assert {t, t} == {t}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class TestState:
    def test_basic_construction(self):
        s = State(name="planning")
        assert s.name == "planning"
        assert s.description == ""
        assert s.invariants == ()
        assert s.transitions == {}

    def test_with_all_fields(self):
        t = Transition(name="start", to="executing")
        s = State(
            name="ready",
            description="Sprint is ready to execute.",
            invariants=["has_tickets", "is_approved"],
            transitions={"start": t},
        )
        assert s.description == "Sprint is ready to execute."
        assert s.invariants == ("has_tickets", "is_approved")
        assert s.transitions["start"] is t

    def test_list_invariants_normalised_to_tuple(self):
        s = State(name="x", invariants=["a"])
        assert isinstance(s.invariants, tuple)

    def test_immutable_name(self):
        s = State(name="planning")
        with pytest.raises(FrozenInstanceError):
            s.name = "other"  # type: ignore[misc]

    def test_transitions_dict_is_independent_copy(self):
        """Mutation of the original dict must not affect the stored one."""
        original = {"start": Transition(name="start", to="x")}
        s = State(name="z", transitions=original)
        original["extra"] = Transition(name="extra", to="y")
        assert "extra" not in s.transitions


# ---------------------------------------------------------------------------
# Machine
# ---------------------------------------------------------------------------


class TestMachine:
    def test_basic_construction(self):
        m = Machine(
            name="ticket",
            context_type="clasi.state_machine.context.TicketContext",
            initial="new",
        )
        assert m.name == "ticket"
        assert m.context_type == "clasi.state_machine.context.TicketContext"
        assert m.initial == "new"
        assert m.states == {}

    def test_with_states(self):
        s = State(name="new")
        m = Machine(
            name="ticket",
            context_type="clasi.state_machine.context.TicketContext",
            initial="new",
            states={"new": s},
        )
        assert m.states["new"] is s

    def test_immutable(self):
        m = Machine(name="x", context_type="y", initial="z")
        with pytest.raises(FrozenInstanceError):
            m.name = "other"  # type: ignore[misc]

    def test_states_dict_is_independent_copy(self):
        original = {"new": State(name="new")}
        m = Machine(name="t", context_type="c", initial="new", states=original)
        original["extra"] = State(name="extra")
        assert "extra" not in m.states


# ---------------------------------------------------------------------------
# TransitionResult
# ---------------------------------------------------------------------------


class TestTransitionResult:
    def test_fireable_result(self):
        r = TransitionResult(name="approve", to="active", fireable=True)
        assert r.fireable is True
        assert r.blocked_by == ()

    def test_blocked_result(self):
        r = TransitionResult(
            name="approve",
            to="active",
            fireable=False,
            blocked_by=["is_reviewed", "has_no_open_issues"],
        )
        assert r.fireable is False
        assert r.blocked_by == ("is_reviewed", "has_no_open_issues")

    def test_list_blocked_by_normalised_to_tuple(self):
        r = TransitionResult(name="x", to="y", fireable=False, blocked_by=["a"])
        assert isinstance(r.blocked_by, tuple)

    def test_immutable(self):
        r = TransitionResult(name="x", to="y", fireable=True)
        with pytest.raises(FrozenInstanceError):
            r.fireable = False  # type: ignore[misc]

    def test_hashable(self):
        r = TransitionResult(name="x", to="y", fireable=True)
        assert hash(r) is not None


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class TestExceptions:
    def test_all_derive_from_state_machine_error(self):
        for exc_class in (
            MachineSyntaxError,
            DuplicatePredicateError,
            UnknownPredicateError,
            NoMatchingStateError,
            AmbiguousStateError,
        ):
            assert issubclass(exc_class, StateMachineError), (
                f"{exc_class.__name__} must derive from StateMachineError"
            )

    def test_state_machine_error_derives_from_exception(self):
        assert issubclass(StateMachineError, Exception)

    def test_raise_and_catch_via_base(self):
        for exc_class in (
            MachineSyntaxError,
            DuplicatePredicateError,
            UnknownPredicateError,
            NoMatchingStateError,
            AmbiguousStateError,
        ):
            with pytest.raises(StateMachineError):
                raise exc_class("test")

    def test_exceptions_carry_message(self):
        exc = UnknownPredicateError("is_missing_predicate")
        assert "is_missing_predicate" in str(exc)
