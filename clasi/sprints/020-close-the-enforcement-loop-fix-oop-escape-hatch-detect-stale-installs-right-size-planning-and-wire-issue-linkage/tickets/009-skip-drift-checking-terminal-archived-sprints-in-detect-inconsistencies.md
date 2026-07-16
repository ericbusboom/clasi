---
id: 009
title: Skip drift-checking terminal/archived sprints in detect_inconsistencies
status: open
use-cases: [SUC-009]
depends-on: []
github-issue: ''
issue: detect-inconsistencies-drift-checks-terminal-archived-sprints.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Skip drift-checking terminal/archived sprints in detect_inconsistencies

## Description

`detect_inconsistencies` (`src/clasi/status/inconsistency.py:37`) compares
declared-vs-computed state for every sprint, including archived ones under
`clasi/sprints/done/`. `closed` is the state machine's only terminal state
with zero outbound transitions (verified), so a drift report on an
archived sprint has no useful answer. The 18 sprints in `sprints/done/`
were archived with legacy `status: done` (fixed at the source by
`019-007`, but not retroactively corrected — that bulk-rewrite was
explicitly cut by stakeholder decision during 019, see
`docs/architecture/architecture-update-019.md` Design Rationale). Each of
those 18 is therefore reported as permanent `state_drift` forever.

**Priority: low, no visible symptom** — `019-006` already excludes
`done/` from status-block assembly, so these 18 warnings don't currently
reach anyone. This ticket fixes the class of defect (a checker asking a
question with no useful answer) so it doesn't resurface if
`detect_inconsistencies` gains another consumer that doesn't filter
`done/`.

**Do NOT resurrect the bulk-rewrite** of the 18 archived files' frontmatter
— explicitly rejected by the stakeholder in 019. The archive is a record
of what happened; those sprints genuinely were archived carrying `status:
done`. Fix the checker, not the data.

## Acceptance Criteria

- [ ] A sprint archived via `Sprint.archive()` with legacy `status: done`
      in its frontmatter produces zero `state_drift` entries from
      `detect_inconsistencies`.
- [ ] A non-terminal sprint whose declared status genuinely disagrees with
      its computed state STILL reports drift — the fix must not
      over-broadly silence live drift, only terminal-state drift. This is
      the assertion that matters most; a skip that's too broad is worse
      than the current noise.
- [ ] The 18 archived files remain byte-for-byte unmodified on disk
      (`grep -lc "^status: done" clasi/sprints/done/*/sprint.md` still
      returns 18 after this ticket).
- [ ] Terminal state is derived from `sprint.yaml`, not hardcoded —
      reuse or promote `_load_terminal_sprint_state` from
      `tests/unit/test_sprint.py` (added by `019-007`) rather than
      reimplementing the lookup.

## Implementation Plan

**Approach**: In `detect_inconsistencies`'s sprint iteration
(`inconsistency.py:57-63`, calling `_check_sprint` at `:89-104`), skip
`_check_sprint` for any sprint whose computed state matches the state
machine's terminal state (derived from `sprint.yaml`, not hardcoded
`"closed"`).

**Files likely involved**: `src/clasi/status/inconsistency.py`,
`tests/unit/test_sprint.py` (promote `_load_terminal_sprint_state` out of
the test module into a shared location if that's cleaner than duplicating
it).

**Testing plan**: Real fixture — an actual archived sprint directory with
legacy `status: done` frontmatter (model on one of the 18 real
`sprints/done/*/sprint.md` files, or a copy of one), asserting zero drift;
a second real non-terminal sprint fixture with genuinely mismatched
declared/computed state, asserting drift still fires.

**Documentation updates**: None required — this is an internal checker
correctness fix with no user-facing behavior change beyond removing false
positives.
