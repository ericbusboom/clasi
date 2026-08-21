# Bump version, commit, tag, and push to remote
push:
    dotconfig version bump --push

# Fast default developer test loop (ticket 032/008). No coverage
# collection (pyproject.toml's addopts no longer welds --cov=... in, so
# this is now just a bare `uv run pytest`) and the `-m 'not slow'`
# addopts filter excludes the real-filesystem/real-git/subprocess tiers
# marked `@pytest.mark.slow` -- see pyproject.toml's `markers` entry and
# the marked test files themselves. Target: under a minute.
test:
    uv run pytest

# Full suite, with coverage -- the sprint-close gate (ticket 032/008).
# `-m 'slow or not slow'` overrides addopts' `-m 'not slow'` filter to
# collect and run everything the fast `test` recipe above skips, and adds
# back the coverage flags this ticket removed from default addopts so
# they don't disappear, just move here. close_sprint's own default
# test_command (see close.py's SprintCloser.run, the `else` branch that
# used to be `["uv", "run", "pytest"]`) is kept in exact sync with this
# recipe's invocation -- the sprint gate must keep running everything
# with coverage even though the bare `uv run pytest` default above no
# longer does. If you change this recipe's pytest invocation, update
# that default in close.py to match, or the gate silently weakens.
test-all:
    uv run pytest -m 'slow or not slow' --cov=src/clasi --cov-report=term-missing --cov-report=lcov:lcov.info

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
