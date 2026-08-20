---
id: '007'
title: 'status sweep excludes terminal sprints: widen exclude_done to closed / archived'
status: open
use-cases: [SUC-001]
depends-on: ['003']
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

- [ ] `_build_sprints_block`'s exclusion check recognizes both
      `status: done` and `status: closed` (or, preferably, a computed
      "is this sprint in a terminal state" check rather than an
      enumerated string list, so a future terminal status doesn't
      require another point fix) as excludable when `exclude_done` is
      set.
- [ ] Sprints physically located under `clasi/sprints/done/` are
      skipped by the sweep regardless of their declared `status:` value
      — do not rely on frontmatter alone when the directory location
      already signals archived state.
- [ ] Call-count assertion: for this repo's fixture (7 sprints, 6 of
      them archived under `done/`), a status-inject invocation with
      `exclude_done` active evaluates only the 1 non-terminal sprint —
      `get_sprint()` and `read_frontmatter()` call counts drop
      accordingly (from about 137/1,816 to counts consistent with
      evaluating 1 sprint, not 7), verified via a debug counter or mock
      call-count assertion, not just wall-clock variance.
- [ ] `time clasi hook status-inject < captured-payload.json` in this
      repo: under 200ms (median), closing the sprint's success
      criterion that ticket 003 alone did not reach.
- [ ] `clasi status` (the CLI command, which always passes
      `exclude_done=False` per `build_status`'s own docstring) is
      unchanged — this ticket only affects the `exclude_done=True` path
      used by the status-inject hook.
- [ ] Existing tests are not weakened: any existing test asserting
      `done`-status exclusion behavior continues to pass unchanged;
      this ticket only widens the check, it does not narrow it.
- [ ] New regression test fixture includes at least one sprint with
      `status: closed` under a `done/` directory and confirms it is
      excluded from the sweep the same way a `status: done` sprint is.

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
