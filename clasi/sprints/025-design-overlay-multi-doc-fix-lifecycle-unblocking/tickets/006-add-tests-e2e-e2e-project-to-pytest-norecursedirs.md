---
id: '006'
title: Add tests/e2e/e2e-project to pytest norecursedirs
status: open
use-cases: []
depends-on: []
github-issue: ''
issue: norecursedirs-stale-e2e-project-breaks-bare-pytest-and-close-sprint.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add tests/e2e/e2e-project to pytest norecursedirs

## Description

Trivial, independent of the design-overlay work above (no architectural
impact — see sprint.md Sizing Decision). `pyproject.toml`'s
`norecursedirs` (~L46) lists `tests/e2e/project` and
`tests/e2e/repro_project` but not `tests/e2e/e2e-project`, the nested
standalone "guessing-game" project introduced by the sprint-023
e2e-harness rework. A bare `uv run pytest` from the repo root tries to
collect that nested project's `tests/` modules and fails with 6
collection errors, breaking both ad-hoc test runs and `close_sprint`'s
default `test_command` gate.

## Acceptance Criteria

- [ ] `tests/e2e/e2e-project` added to `norecursedirs` in
      `pyproject.toml`.
- [ ] `uv run pytest --co -q` from the repo root collects with 0 errors.
- [ ] Audit whether `tests/e2e/project` and `tests/e2e/repro_project`
      (the two existing entries) still exist on disk; if either is
      stale, note it in this ticket (removing a stale-but-harmless
      entry is optional cleanup, not required for the acceptance
      criteria above — do not expand scope chasing it if it turns out
      to be a larger rename than expected).

## Testing

- **Existing tests to run**: `uv run pytest --co -q` (collection only,
  confirms the fix); `uv run pytest tests/unit tests/integration
  tests/system` (full existing scoped suite, confirms no regression).
- **New tests to write**: none — this is a config change; the
  verification is that collection succeeds, not a new test asserting
  config content.
- **Verification command**: `uv run pytest` (bare, from repo root —
  this is the exact command whose failure this ticket fixes; passing
  bare is the ticket's own acceptance signal, not just the scoped
  fallback).
