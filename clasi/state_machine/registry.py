"""Global predicate registry for the CLASI state machine engine.

Predicates are pure callables that answer yes/no questions about a
context object.  They are registered at import time via the
:func:`predicate` decorator and looked up by name at evaluation time.

Typical usage::

    # In clasi/state_machine/predicates/ticket.py
    from clasi.state_machine.registry import predicate

    @predicate("is_ticket_done")
    def is_ticket_done(ctx):
        return ctx.status == "done"

The decorator **does not wrap the function** — it returns the original
callable unchanged after storing a reference in the module-level registry.

.. warning::

    :func:`clear_registry` is provided for test isolation only.  Do not
    call it in production code.  The registry is intended to be write-once:
    all modules register their predicates at import time, and the registry
    is then read-only for the lifetime of the process.
"""

from __future__ import annotations

from typing import Callable

from clasi.state_machine.models import DuplicatePredicateError, UnknownPredicateError

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Callable] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def predicate(name: str) -> Callable:
    """Decorator that registers a callable under *name* in the global registry.

    The decorated function is returned **unchanged** — the decorator adds a
    side effect (registration) but does not modify or wrap the callable.

    Args:
        name: The registry key for this predicate (e.g.
            ``"is_architecture_present"``).  Must be unique across the entire
            process; registering the same name twice raises
            :class:`~clasi.state_machine.models.DuplicatePredicateError`.

    Returns:
        A decorator that registers the target function and returns it as-is.

    Raises:
        DuplicatePredicateError: If *name* is already present in the registry.

    Example::

        @predicate("is_foo")
        def is_foo(ctx):
            return ctx.foo

    .. warning::

        ``clear_registry()`` is test-only.  Do not call it in production.
    """

    def decorator(fn: Callable) -> Callable:
        if name in _REGISTRY:
            raise DuplicatePredicateError(
                f"Predicate {name!r} is already registered. "
                "Each predicate name must be unique."
            )
        _REGISTRY[name] = fn
        return fn

    return decorator


def get_predicate(name: str) -> Callable:
    """Return the callable registered under *name*.

    Args:
        name: The predicate name to look up.

    Returns:
        The callable that was registered via :func:`predicate`.

    Raises:
        UnknownPredicateError: If *name* has not been registered.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        raise UnknownPredicateError(
            f"No predicate named {name!r} is registered. "
            f"Registered predicates: {sorted(_REGISTRY)}"
        ) from None


def list_predicates() -> list[str]:
    """Return all registered predicate names in sorted order.

    Returns:
        A new sorted list of predicate name strings.  Empty list if no
        predicates have been registered yet.
    """
    return sorted(_REGISTRY.keys())


def clear_registry() -> None:
    """Remove all entries from the global registry.

    **Test use only.**  Call this in test teardown (or a pytest fixture)
    to prevent predicate registrations in one test from leaking into
    another.  Never call this in production code.
    """
    _REGISTRY.clear()
