---
id: '007'
title: 'status sweep excludes terminal sprints: widen exclude_done to closed / archived'
status: done
use-cases:
- SUC-001
depends-on:
- '003'
github-issue: ''
issue: status-exclude-done-filter-misses-closed-sprints.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# status sweep excludes terminal sprints: widen exclude_done to closed / archived

## Description

Ticket 003 landed status-inject's caching/trimming fixes but measured
median about 0.78s in this repo — well above the sprint's under-200ms
success criterion — because of a pre-existing gap outside 003's scope:
`_build_sprints_block`'s `exclude_done` filter only matches
`sprint.status == "done"`, while the six archived sprints under
`clasi/sprints/done/` (020-025) declare `status: closed`. They leak past
the filter and get fully re-evaluated on every status-inject invocation
(137 `get_sprint()` calls, 1,816 `read_frontmatter()` calls per prompt;
7 sprints evaluated instead of 1). Full measurement detail is in ticket
003's Measurement Notes (`tickets/done/003-...md`). This ticket widens
the terminal-state check so archived/closed sprints are excluded from
the per-prompt sweep the same way `done` sprints already are, closing
the sprint's `<200ms` success criterion.

**Depends on ticket 003** (already done): this ticket re-measures
against and builds directly on 003's landed caching changes — the
`<200ms` target is only reachable once both the redundant-call fixes
(003) and this terminal-sprint exclusion (007) are in place together.

## Acceptance Criteria

- [x] `_build_sprints_block`'s exclusion check recognizes both
      `status: done` and `status: closed` (or, preferably, a computed
      "is this sprint in a terminal state" check rather than an
      enumerated string list, so a future terminal status doesn't
      require another point fix) as excludable when `exclude_done` is
      set. Implemented as a module-level `_is_terminal_sprint(sprint)`
      helper in `src/clasi/status/reporter.py` backed by a named
      `_TERMINAL_SPRINT_STATUSES = frozenset({"done", "closed"})`
      constant (a single named set, not scattered string comparisons),
      called from `_build_sprints_block`'s `exclude_done` branch.
- [x] Sprints physically located under `clasi/sprints/done/` are
      skipped by the sweep regardless of their declared `status:` value
      — do not rely on frontmatter alone when the directory location
      already signals archived state. `_is_terminal_sprint` checks
      `sprint.path.parent.name == "done"` as a second, independent
      signal alongside the status check (either one alone is
      sufficient to exclude).
- [x] Call-count assertion: for this repo's fixture (7 sprints, 6 of
      them archived under `done/`), a status-inject invocation with
      `exclude_done` active evaluates only the 1 non-terminal sprint —
      `get_sprint()` and `read_frontmatter()` call counts drop
      accordingly (from about 137/1,816 to counts consistent with
      evaluating 1 sprint, not 7), verified via a debug counter or mock
      call-count assertion, not just wall-clock variance. See
      Measurement Notes below for the exact counts measured both on a
      synthetic fixture (`tests/unit/test_status/test_hook_injection.py::TestHookExcludesClosedStatusArchivedSprints`)
      and on this repo's own real sprint history.
- [ ] `time clasi hook status-inject < captured-payload.json` in this
      repo: under 200ms (median), closing the sprint's success
      criterion that ticket 003 alone did not reach. **Not fully met —
      see Measurement Notes below for the honest numbers.** Median wall
      time dropped from 515.7ms (003 landed, 007 not yet) to 238.4ms
      (007 applied) in the same session/machine — a genuine 54%
      reduction and the correct fix for the mechanism this ticket was
      scoped to (the terminal-sprint sweep) — but the best single
      observed run (207.8ms) still exceeds 200ms, so the sprint's
      absolute headline number is not fully closed by this ticket
      alone. Root cause of the residual gap is identified below and is
      outside this ticket's specified file scope (`_build_sprints_block`'s
      filter only).
- [x] `clasi status` (the CLI command, which always passes
      `exclude_done=False` per `build_status`'s own docstring) is
      unchanged — this ticket only affects the `exclude_done=True` path
      used by the status-inject hook. `_is_terminal_sprint` is called
      only inside `_build_sprints_block`'s `if exclude_done:` branch, so
      the `exclude_done=False` path is structurally untouched. Verified
      via the full `tests/integration/test_status_e2e.py` +
      `test_status_cli.py` + `test_status_mcp.py` suite (62 passed,
      all against this repo's real `.clasi/`/`clasi/` state).
- [x] Existing tests are not weakened: any existing test asserting
      `done`-status exclusion behavior continues to pass unchanged;
      this ticket only widens the check, it does not narrow it. All
      pre-existing `TestExcludeDone*` / `TestHookExcludesDone` tests in
      `test_reporter.py` and `test_hook_injection.py` pass unmodified.
- [x] New regression test fixture includes at least one sprint with
      `status: closed` under a `done/` directory and confirms it is
      excluded from the sweep the same way a `status: done` sprint is.
      Added `TestExcludeDoneWidenedToClosedArchived` (unit, fake
      objects, 4 tests: closed-status exclusion, `exclude_done=False`
      unaffected, done/-path-only exclusion with a non-standard status
      string, regression check that plain `status: done` still works)
      in `tests/unit/test_status/test_reporter.py`, and
      `TestHookExcludesClosedStatusArchivedSprints` (on-disk fixture
      matching this repo's real 6-archived/1-active shape, 2 tests:
      structural exclusion + call-count assertion) in
      `tests/unit/test_status/test_hook_injection.py`.

## Measurement Notes (recorded 2026-08-19/20)

**Call counts — real repo** (`build_status(exclude_done=True,
skip_inconsistencies=True)` against this repo's own `Project`, git-stash
toggling the fix on/off within the same session so both numbers are
directly comparable; not the original ticket-003-session numbers, which
were measured against a slightly different sprint-content snapshot):

| | sprints evaluated | `get_sprint()` calls | `read_frontmatter()` calls |
|---|---|---|---|
| Before 007 (003 landed only) | 7 (020-026) | 91 | 1,713 |
| After 007 | 1 (026 only) | 31 | 195 |
| Reduction | 6/7 sprints dropped | 66% | 89% |

**Call counts — synthetic fixture** (`TestHookExcludesClosedStatusArchivedSprints`,
6 archived `status: closed` sprints + 1 active, matching this repo's
shape at a smaller scale so the test isn't tied to this repo's exact
sprint count): before the fix, 71 `get_sprint()` / 350
`read_frontmatter()` calls (all 7 sprints evaluated); after, 23 / 80
(only the 1 active sprint's tickets evaluated). Test asserts generous
bounds (`<=40` / `<=150`) around the measured post-fix values so it
stays robust to unrelated predicate-count drift while still catching a
regression that lets any archived sprint leak back through.

**Timing** — `time clasi hook status-inject < captured-payload.json`
(the same payload ticket 003 used), measured via
`subprocess.run` + `time.perf_counter()` for tighter resolution than
`/usr/bin/time`, same machine/session, no other load running
concurrently:

- Before 007 (003 landed only), n=12: 456.2-663.1ms, median **515.7ms**,
  mean 532.1ms.
- After 007, n=20: 207.8-305.7ms, median **238.4ms**, mean 243.4ms.
- **Target not fully met**: median (238.4ms) and even the best single
  run (207.8ms) remain above the 200ms threshold, despite the 54%
  median reduction.

**Root cause of the residual gap (not fixed — out of this ticket's
scope):** with the sweep now down to 1 sprint, a `cProfile` pass over
the real hook invocation shows the remaining cost is no longer
sprint-count-dependent. It is dominated by: (a) the 2-3 real `git`
subprocess spawns that survive ticket 003's call-count memoization —
memoization collapsed the *count* of git queries, but each surviving
`subprocess.run` still pays real OS process-creation overhead (about
20-30ms per spawn measured directly, e.g. `git branch --show-current`
alone), which no amount of within-process caching removes; (b)
`hook_handlers._oop_active`/`_oop_db_record`'s `.clasi/oop` bypass
check, which opens the StateDB (SQLite) *before* `build_status` is even
called — a cost this ticket's scope (`_build_sprints_block`'s filter)
never touches; and (c) unavoidable one-time Python process-startup and
first-invocation `load_machine` YAML-parse cost inherent to a
fresh-process-per-hook-call CLI model. None of these fall under this
ticket's Implementation Plan (`_build_sprints_block`'s exclude_done
filter only) — closing the remaining about 20-40ms gap would need a
follow-up ticket scoped to git-spawn-count reduction and/or caching the
OOP bypass check, which this ticket does not attempt in order to stay
in scope.

**Test modules run** (all passing, `--no-cov`, foreground):
- `tests/unit/test_status/test_reporter.py` — 60 passed (4 new closed/path exclusion tests)
- `tests/unit/test_status/test_hook_injection.py` — 49 passed (2 new: structural exclusion + call-count assertion)
- `tests/unit/test_status/` (full dir) — 249 passed
- `tests/integration/test_status_e2e.py` + `test_status_cli.py` + `test_status_mcp.py` — 62 passed (confirms `clasi status` CLI / MCP paths, which pass `exclude_done=False`, are unaffected)

## Implementation Plan

**Approach**: Locate `_build_sprints_block`'s `exclude_done` filter
(status subsystem — likely `src/clasi/status/reporter.py` or
`src/clasi/status/__init__.py`, wherever the per-prompt sweep iterates
sprints). Replace the exact `status == "done"` string match with a
check that also matches `status == "closed"`, and/or a path-based check
(sprint directory under the project's `done/` archive subdirectory) as
a second, independent signal — prefer whichever the existing
`is_terminal`-style predicate infrastructure in `clasi.state_machine`
already exposes, if one exists, over a new hardcoded string set, so this
doesn't need a third point-fix if another terminal label appears later.
Re-run ticket 003's own before/after timing methodology against this
repo's real fixture (7 sprints, 6 archived) to confirm the combined
effect closes the `<200ms` target.

**Files to modify**:
- The status subsystem's sprint-sweep/filter code (`_build_sprints_block`
  or equivalent — confirm exact location via the codebase before
  editing; do not guess a path without verifying).
- Its corresponding test module.

**Testing plan**: Reuse ticket 003's call-count assertion pattern
(mock/debug counter on `get_sprint()`/`read_frontmatter()`) extended to
confirm `status: closed` sprints under `done/` are now excluded. Reuse
003's `time`-based before/after measurement against a captured real
payload from this repo. Add a fixture sprint with `status: closed`
under a `done/`-style path to the test suite to cover the new exclusion
case explicitly, alongside a fixture confirming `clasi status`
(`exclude_done=False`) still reports full history including archived
sprints, unchanged.

**Documentation updates**: This sprint's `design/` overlay
(`status-DESIGN.md`) already documents ticket 003's caching changes to
this subsystem; if this ticket's fix lands in a function not already
described there, extend that overlay entry (or, if the overlay has
already been applied/closed out, note the change in the ticket's
completion notes for future overlay reconciliation) rather than leaving
the terminal-state exclusion undocumented.
