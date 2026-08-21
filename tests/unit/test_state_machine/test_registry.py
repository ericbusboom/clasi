"""Unit tests for clasi.state_machine.registry.

Covers: register, lookup, list, duplicate-name error, unknown-name error,
and ``clear_registry`` teardown isolation.

Registry isolation between tests (and between this module and whatever
runs after it in the same pytest process) is provided by the autouse
``_clean_registry`` fixture in this package's ``conftest.py`` — see that
file's docstring for why it's a snapshot/restore fixture rather than a
plain clear.
"""

from __future__ import annotations

import pytest

from clasi.state_machine.models import DuplicatePredicateError, UnknownPredicateError
from clasi.state_machine.registry import (
    clear_registry,
    get_predicate,
    list_predicates,
    predicate,
)


# ---------------------------------------------------------------------------
# Registration via @predicate decorator
# ---------------------------------------------------------------------------


class TestPredicateDecorator:
    def test_decorator_registers_function(self):
        @predicate("is_foo")
        def is_foo(ctx):
            return True

        assert "is_foo" in list_predicates()

    def test_decorator_returns_original_function_unchanged(self):
        """The decorator must not wrap the function — identity check."""

        def is_bar(ctx):
            return False

        result = predicate("is_bar")(is_bar)
        assert result is is_bar

    def test_registered_function_is_callable(self):
        @predicate("is_baz")
        def is_baz(ctx):
            return ctx == "yes"

        fn = get_predicate("is_baz")
        assert fn("yes") is True
        assert fn("no") is False

    def test_multiple_predicates_registered_independently(self):
        @predicate("pred_a")
        def pred_a(ctx):
            return True

        @predicate("pred_b")
        def pred_b(ctx):
            return False

        assert get_predicate("pred_a") is pred_a
        assert get_predicate("pred_b") is pred_b


# ---------------------------------------------------------------------------
# Duplicate registration
# ---------------------------------------------------------------------------


class TestDuplicateRegistration:
    def test_duplicate_name_raises(self):
        @predicate("is_dup")
        def first(ctx):
            return True

        with pytest.raises(DuplicatePredicateError):

            @predicate("is_dup")
            def second(ctx):
                return False

    def test_duplicate_error_message_contains_name(self):
        @predicate("is_named_pred")
        def first(ctx):
            return True

        with pytest.raises(DuplicatePredicateError) as exc_info:

            @predicate("is_named_pred")
            def second(ctx):
                return False

        assert "is_named_pred" in str(exc_info.value)

    def test_duplicate_does_not_overwrite_original(self):
        """Original registration must survive the failed duplicate attempt."""

        @predicate("is_kept")
        def original(ctx):
            return True

        with pytest.raises(DuplicatePredicateError):

            @predicate("is_kept")
            def interloper(ctx):
                return False

        # Registry still points at the original.
        assert get_predicate("is_kept") is original


# ---------------------------------------------------------------------------
# Lookup via get_predicate
# ---------------------------------------------------------------------------


class TestGetPredicate:
    def test_returns_registered_callable(self):
        @predicate("is_lookup_target")
        def fn(ctx):
            return True

        assert get_predicate("is_lookup_target") is fn

    def test_unknown_name_raises(self):
        with pytest.raises(UnknownPredicateError):
            get_predicate("nonexistent_predicate")

    def test_unknown_name_error_contains_name(self):
        with pytest.raises(UnknownPredicateError) as exc_info:
            get_predicate("missing_name")

        assert "missing_name" in str(exc_info.value)

    def test_empty_registry_raises_unknown(self):
        # Registry is cleared by fixture — should raise immediately.
        with pytest.raises(UnknownPredicateError):
            get_predicate("any_name")


# ---------------------------------------------------------------------------
# Listing via list_predicates
# ---------------------------------------------------------------------------


class TestListPredicates:
    def test_returns_empty_list_when_empty(self):
        assert list_predicates() == []

    def test_returns_sorted_names(self):
        @predicate("zebra")
        def z(ctx):
            return True

        @predicate("apple")
        def a(ctx):
            return True

        @predicate("mango")
        def m(ctx):
            return True

        assert list_predicates() == ["apple", "mango", "zebra"]

    def test_returns_new_list_each_call(self):
        """Callers must not be able to mutate the registry via the returned list."""

        @predicate("is_single")
        def fn(ctx):
            return True

        result1 = list_predicates()
        result1.append("injected")
        result2 = list_predicates()

        assert "injected" not in result2

    def test_reflects_current_registrations(self):
        assert list_predicates() == []

        @predicate("first")
        def f(ctx):
            return True

        assert list_predicates() == ["first"]

        @predicate("second")
        def s(ctx):
            return True

        assert list_predicates() == ["first", "second"]


# ---------------------------------------------------------------------------
# clear_registry (test isolation helper)
# ---------------------------------------------------------------------------


class TestClearRegistry:
    def test_clear_empties_registry(self):
        @predicate("to_be_cleared")
        def fn(ctx):
            return True

        assert list_predicates() == ["to_be_cleared"]
        clear_registry()
        assert list_predicates() == []

    def test_clear_allows_same_name_to_be_re_registered(self):
        """After clear, duplicate-name check should pass again."""

        @predicate("reusable")
        def first(ctx):
            return True

        clear_registry()

        # Must not raise DuplicatePredicateError.
        @predicate("reusable")
        def second(ctx):
            return False

        assert get_predicate("reusable") is second

    def test_clear_on_empty_registry_is_safe(self):
        # Already empty from fixture; second clear should not raise.
        clear_registry()
        assert list_predicates() == []
