---
status: pending
---

# 4 pre-existing failures in tests/unit/test_sprint.py TestRealDoneArchiveBackwardCompat

## Description

The repository test suite is not green on the current mainline. Four
tests fail in `tests/unit/test_sprint.py::TestRealDoneArchiveBackwardCompat`:

    uv run pytest → 4 failed, 2703 passed (~462s)

Discovered during sprint 023 execution (2026-07-17): the ticket-001
programmer ran the suite, then stashed all ticket changes and re-ran
against the clean sprint-branch baseline (cut from master the same day)
— the identical 4 failures reproduced, so they predate sprint 023 and
are unrelated to `tests/e2e/` harness work.

## Cause

Not yet diagnosed. The test-class name suggests backward-compatibility
coverage of the sprint done-archive layout (`clasi/sprints/done/`), an
area touched by recent artifact-layout sprints (020–022) — plausibly the
same family as the declared-closed/computed-pre-flight state drift those
sprints exhibit, but that is conjecture until someone reads the failures.

## Proposed fix

Diagnose the four failures and either fix the code they exercise or
update the tests to the current done-archive contract. Whichever way it
resolves, mainline should return to a green suite — every sprint's
tests-pass gate is degraded while a known-red baseline has to be
special-cased.

## Verification

- `uv run pytest tests/unit/test_sprint.py -k TestRealDoneArchiveBackwardCompat` passes.
- Full suite green with no baseline carve-outs.

## Related

- Observed during sprint 023 (ticket 001 verification).
- Possibly related: sprints 020–022 declared-closed/computed-pre-flight
  state drift reported by the status hook.
