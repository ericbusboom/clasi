---
status: done
sprint: '025'
tickets:
- 025-006
---

# norecursedirs is stale: bare `uv run pytest` fails collection on tests/e2e/e2e-project

## Description

`pyproject.toml`'s `norecursedirs` lists `tests/e2e/project` and
`tests/e2e/repro_project` but **not** `tests/e2e/e2e-project` — a nested,
standalone project ("guessing-game", with its own `pyproject.toml`) that
the sprint-023 e2e-harness rework introduced. Its `tests/` directory
contains modules like `test_menu.py`, `test_smoke.py`, `test_number_game.py`
whose names collide with the parent suite's import machinery.

When the parent suite is collected from the repo root, pytest tries to
import those nested modules and hits `ModuleNotFoundError: No module named
'tests.test_menu'` (and five siblings) → **6 collection errors → pytest
exit code 2**.

## Impact

- **`close_sprint`'s default `test_command` (`uv run pytest`) fails at the
  tests step for every CLASI sprint close in this repo.** Sprint 024's
  close was blocked by exactly this until worked around with an explicit
  scoped command: `uv run pytest tests/unit tests/integration tests/system`.
- Any developer running the bare suite from the repo root hits the same 6
  collection errors and a non-zero exit, obscuring real results.

## Reproduction

```
uv run pytest --co -q
# ...
# ERROR tests/e2e/e2e-project/tests/test_menu.py
# ERROR tests/e2e/e2e-project/tests/test_smoke.py
# ... 6 errors during collection
```

The scoped invocation collects cleanly (2436 tests, 0 errors):

```
uv run pytest tests/unit tests/integration tests/system --co -q
```

## Proposed fix

- Add `tests/e2e/e2e-project` to `norecursedirs` in `pyproject.toml`.
- Audit whether the sprint-023 rename/rework left other stale
  `norecursedirs` entries (the two currently listed, `tests/e2e/project`
  and `tests/e2e/repro_project`, may themselves no longer exist on disk).
- Consider whether `close_sprint`'s default `test_command` should target
  the real test roots explicitly rather than a bare `uv run pytest`, so a
  future stray nested project can't silently break every close.

## Context

Discovered during the sprint 024 close on 2026-07-20. Independent of
sprint 024's own scope (guard/gate correctness), surfaced because
sprint 024's ticket 007 made the close's test timeout configurable, which
put the close's test-run behavior under close inspection.
