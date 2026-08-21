---
id: '005'
title: Fix predicate-registry test-order pollution
status: open
use-cases: ["SUC-004"]
depends-on: []
github-issue: ''
issue: test-suite-predicate-registry-pollution.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix predicate-registry test-order pollution

## Description

Concatenating test modules in a non-default order (specifically
`tests/unit/test_state_machine/` before
`tests/integration/test_state_machine_smoke.py`) fails with
`UnknownPredicateError: Registered predicates: []`. Root cause,
identified during this sprint's planning pass by reading the actual
fixtures (not just the issue's description): three `_clean_registry`
autouse fixtures each call `clear_registry()` on teardown with nothing
to repopulate it for whichever test module runs next in the same
process:

- `tests/unit/test_state_machine/test_registry.py:26-34` — `clear_registry()`
  before and after every test; the module never re-imports the real
  predicate modules, since its own tests register throwaway predicates
  directly via `@predicate(...)` in test bodies.
- `tests/unit/test_state_machine/test_evaluator.py:33-39` — same shape,
  also with throwaway in-test predicates.
- `tests/unit/test_state_machine/test_predicates.py:44-55` — this one
  *does* repopulate the registry, but only at **setup** (via
  `importlib.reload` of `clasi.state_machine.predicates.{project,sprint,ticket}`)
  for its own tests; its `yield`-then-`clear_registry()` teardown still
  leaves the registry empty for whatever runs after it.

None of the three restores the registry to what it held *before* that
module ran — they each leave it empty when their own tests are done.
`tests/integration/test_state_machine_smoke.py` (or any other module
exercising the real state machine) then finds an empty registry if it
happens to run afterward in the same process — order-dependent by
construction, not by accident.

This does not reproduce under the natural full-suite collection order
(alphabetical: `integration/` collects before `unit/state_machine`'s
teardown has a chance to run first — verify the exact collection-order
mechanics if curious, but it isn't required to fix this), and every
ticket's own scoped test command passes standalone, which is exactly
why this has survived undetected.

## Acceptance Criteria

- [ ] The three `_clean_registry` fixtures (`test_registry.py`,
      `test_evaluator.py`, `test_predicates.py`) restore the registry
      to real, production state on teardown instead of leaving it
      empty. Two implementation shapes are acceptable — pick one and
      apply it consistently across all three files (or centralize into
      one shared fixture all three use, which is the cleaner outcome
      if the ticket's time budget allows):
      (a) **Snapshot/restore**: at setup, save a copy of
      `_REGISTRY` (`clasi.state_machine.registry._REGISTRY`, currently
      a module-level dict); at teardown, clear and restore the saved
      copy. Robust regardless of which predicate modules happen to be
      imported at that point in the process — it undoes exactly what
      the test did, nothing more, nothing less.
      (b) **Explicit re-import**: at teardown (not just at setup, the
      way `test_predicates.py` currently only does at setup), reload
      `clasi.state_machine.predicates.{project,sprint,ticket}` the same
      way `test_predicates.py`'s setup already does, so the real
      predicates are back in place for the next module.
      Prefer (a) unless there's a concrete reason (b) is simpler in
      context — (a) doesn't need to know which modules register
      predicates, so it can't drift out of sync if a new predicate
      module is added later.
- [ ] A new check runs `tests/unit/test_state_machine/` and
      `tests/integration/test_state_machine_smoke.py` (plus any other
      module that evaluates the real state machine — grep for
      `evaluate_state`/`inspect_transitions` callers outside
      `test_state_machine/` to find them) under a deliberately shuffled
      or reversed collection order and passes. A `pytest.ini`/`pyproject.toml`
      addition using `pytest-randomly` is heavier than this needs;
      simplest approach is a one-off invocation ordering test files
      explicitly in reverse (`pytest tests/integration/test_state_machine_smoke.py
      tests/unit/test_state_machine/ -v`) captured as a documented,
      periodically-rerun command (e.g. a comment in the test file or a
      `just` recipe) rather than a new pytest plugin dependency —
      implementer's call on the exact mechanism, but it must be
      something a future contributor can actually re-run, not just
      "verified once during this ticket."
- [ ] The existing, order-independent parts of the suite are unaffected
      — this is a test-isolation-only fix; `state_machine/registry.py`'s
      production code is untouched.

## Implementation Plan

### Approach

1. Read all three fixtures in full (already summarized above from this
   planning pass, but re-verify line numbers before editing — this
   sprint's other tickets don't touch these files, so no drift is
   expected, but confirm).
2. Implement the snapshot/restore fixture (preferred, see Acceptance
   Criteria) — either as a shared fixture in a new or existing
   `tests/unit/test_state_machine/conftest.py`, replacing the three
   duplicated `_clean_registry` fixtures with one import, or as an
   identical fix applied independently to each of the three files if
   consolidating into a shared conftest turns out to be more invasive
   than this ticket's scope warrants (judgment call — a shared conftest
   is the better outcome per DRY, but don't let a refactor beyond the
   three-file fix balloon this ticket).
3. Run the shuffled/reversed-order check and confirm it passes; capture
   it as a documented, re-runnable command.
4. Run the normal (default-order) suite to confirm no regression.

### Files to Modify

- `tests/unit/test_state_machine/test_registry.py`
- `tests/unit/test_state_machine/test_evaluator.py`
- `tests/unit/test_state_machine/test_predicates.py`
- Possibly new: `tests/unit/test_state_machine/conftest.py` (if
  consolidating the three fixtures into one shared one)

### Testing Plan

- **Existing tests to run**: `uv run pytest tests/unit/test_state_machine/
  tests/integration/test_state_machine_smoke.py -v` (default order,
  confirms no regression from the fixture change itself).
- **New tests to write**: none in the traditional sense — the
  "new test" here is the shuffled/reversed-order *invocation*, not a
  new test function. Document the exact command used to verify it
  (e.g. as a comment at the top of `test_registry.py` or wherever the
  shared fixture lives) so it's re-runnable by a future contributor,
  not just something verified once during this ticket.
- **Verification command**: `uv run pytest tests/integration/test_state_machine_smoke.py
  tests/unit/test_state_machine/ -v` (reversed order — this exact
  invocation should fail before the fix and pass after; use it as the
  before/after proof this ticket's fix actually works, not just that
  the normal-order suite still passes).

### Documentation Updates

- None required — this is a test-infrastructure-only fix with no
  user-facing or architectural surface.

## Process Notes

- Guards fail closed. If a role-guard or mcp-guard block is hit while
  working this ticket, **STOP and report it** — do not route around it.
  Reporting a block is a successful outcome of this ticket's work, not
  a failure.
- Tier-2 (in-progress-ticket) write scope covers this ticket's own file
  under the locked sprint's `tickets/` tree, plus `tests/` (a
  `protected_paths` entry).
