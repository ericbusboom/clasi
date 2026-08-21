# Bump version, commit, tag, and push to remote
push:
    dotconfig version bump --push

# Verify the state-machine test suite is order-independent (ticket 032/005).
# Predicate-registry pollution between test modules is silent and
# collection-order-dependent, so a normal pytest run won't catch a
# regression here — this runs the state-machine-touching modules under
# both the collection order that reproduced the original bug and its
# natural order. Re-run this after touching anything in
# tests/unit/test_state_machine/ or its conftest.py.
test-order-check:
    uv run pytest --no-cov tests/unit/test_state_machine/ tests/integration/test_state_machine_smoke.py tests/system/test_worktree_and_planning_integration.py
    uv run pytest --no-cov tests/integration/test_state_machine_smoke.py tests/system/test_worktree_and_planning_integration.py tests/unit/test_state_machine/
