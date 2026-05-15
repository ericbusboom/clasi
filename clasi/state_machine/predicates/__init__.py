"""CLASI state machine predicates.

Importing this package registers all ``is_*`` predicates for the three
state machines (project, sprint, ticket) in the global predicate registry.

Modules are imported in dependency order — project predicates define the
shared ``is_on_sprint_branch`` predicate that is also used by the sprint
machine, so ``project`` must be imported before ``sprint``.

Usage::

    import clasi.state_machine.predicates  # noqa: F401 — side-effect import
    from clasi.state_machine.registry import get_predicate, list_predicates
"""

from clasi.state_machine.predicates import project  # noqa: F401
from clasi.state_machine.predicates import sprint  # noqa: F401
from clasi.state_machine.predicates import ticket  # noqa: F401

__all__ = ["project", "sprint", "ticket"]
