"""Shared fixtures for ``tests/unit/test_state_machine/``.

Registry isolation
-------------------
``clasi.state_machine.registry._REGISTRY`` is process-global, write-once
production state: every predicate module registers itself at import time
and the registry is meant to be read-only for the rest of the process
(see the warning in ``registry.py``). Tests in this package need to
violate that on purpose — registering throwaway predicates, or clearing
the registry outright to test ``clear_registry()`` itself — so each test
needs a private, disposable registry.

The naive way to get that (clear before the test, clear again after) is
what this package used to do, independently, in three files
(``test_registry.py``, ``test_evaluator.py``, ``test_predicates.py``).
That leaves the registry *empty* once the last test in whichever module
runs last finishes, for the rest of the pytest process — order-dependent
by construction, not by accident. Any later module that evaluates the
real state machine (e.g. ``tests/integration/test_state_machine_smoke.py``,
``tests/system/test_worktree_and_planning_integration.py``) then fails
with ``UnknownPredicateError: Registered predicates: []`` if it happens
to run afterward in the same process. See ticket 032/005.

``_clean_registry`` below fixes this at the source: it snapshots
whatever the registry held *before* the test ran and restores exactly
that after the test, regardless of what the test did to the registry in
between. That means this package can never leave the registry in a
different state than it found it, so module collection order stops
mattering — the fix doesn't need to know which predicate modules exist
or when they're imported, so it can't drift out of sync as new predicate
modules are added later (unlike a fixture that re-imports/reloads a
fixed list of module names).

Re-verifying this stays order-independent
------------------------------------------
Run (from repo root)::

    just test-order-check

which runs the state-machine-touching modules under both the failing
collection order this ticket reproduced and the reverse. Both must pass.
"""

from __future__ import annotations

import pytest

from clasi.state_machine import registry as _registry_module


@pytest.fixture(autouse=True)
def _clean_registry():
    """Snapshot/restore the global predicate registry around each test.

    Setup: record whatever ``_REGISTRY`` currently holds, then clear it so
    this test starts from a known-empty, private registry.

    Teardown: clear whatever the test left behind and restore the exact
    snapshot taken at setup — undoing precisely what this test did, no
    more and no less, so the registry is handed to the next test (in this
    module, or any other module later in the same process) exactly as
    this test found it.
    """
    snapshot = dict(_registry_module._REGISTRY)
    _registry_module._REGISTRY.clear()
    yield
    _registry_module._REGISTRY.clear()
    _registry_module._REGISTRY.update(snapshot)
