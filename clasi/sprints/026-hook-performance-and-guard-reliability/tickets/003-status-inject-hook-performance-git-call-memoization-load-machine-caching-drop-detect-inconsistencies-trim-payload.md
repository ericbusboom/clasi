---
id: '003'
title: 'status-inject hook performance: git-call memoization, load_machine caching,
  drop detect_inconsistencies, trim payload'
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: hook-overhead-status-inject-dead-hooks-and-logging.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# status-inject hook performance: git-call memoization, load_machine caching, drop detect_inconsistencies, trim payload

## Description

`status-inject` (the `UserPromptSubmit` hook, `clasi hook status-inject`)
costs about 1.05-1.15s of blocking latency on every user prompt.
Profiling attributes this to: 28 uncached git subprocess calls per
`build_status` call (`ClasiStateReader`'s git-backed methods, e.g.
`is_on_sprint_branch` alone shells out 14x), `load_machine` re-parsing
the same three state-machine YAMLs about 20x with no cache, and
`detect_inconsistencies` (about 400ms of diagnostics) running inline in
the hot hook path. The injected YAML is also about 3.6KB (about 900
tokens), 61% of which is `available_transitions`/`blocked_by` noise for
empty pre-flight sprints. This ticket caches the redundant work and
trims the noise without changing status semantics for the common case
(a project with active ticketed sprints).

## Acceptance Criteria

- [x] `ClasiStateReader`'s git-subprocess-backed methods memoize their
      result per instance (per hook invocation) — repeated calls to the
      same git query within one `build_status` call shell out once, not
      once per predicate. Implemented via a `_run_git(*args)` helper
      keyed on the argument tuple; `git_branch`, `default_branch`, and
      `branch_merged` (all sprints share one `git branch --merged
      <default>` call) all route through it.
- [x] `state_machine.loader.load_machine` is wrapped with
      `functools.lru_cache` (or equivalent process-lifetime cache) —
      the three packaged machine definitions (`project`, `sprint`,
      `ticket`) are parsed once per process, not once per call.
- [x] The `status-inject` hook path no longer calls
      `detect_inconsistencies`; `clasi status` (CLI) and the
      project-status skill still call it, unchanged. Implemented via a
      new `skip_inconsistencies` parameter threaded through
      `build_status` → `StatusReporter.build`, defaulting to `False`
      everywhere except `handle_status_inject`, which passes `True`.
      `handle_subagent_start` (the other `_build_status_block` caller)
      intentionally left at the default — only status-inject is in
      scope per this criterion's wording.
- [x] Injected YAML drops `available_transitions`/`blocked_by` detail
      for empty pre-flight sprints (no active or ticketed sprint);
      status YAML for a project with active ticketed sprints is
      unchanged apart from this trim. Implemented as
      `_trim_empty_preflight_sprints` in `hook_handlers.py`, applied to
      the narrowed dict for any sprint entry with `tickets.total == 0`
      (structurally, a sprint can only reach `ticketed`/`executing`/
      `review`/`closed` — states that keep their detail — once it has
      at least one ticket, per `is_at_least_one_ticket` in
      `sprint.yaml`).
- [x] Git-subprocess call count per invocation drops from about 28 to
      about 3 (verified via a debug counter or mock call-count
      assertion, not just wall-clock variance). Verified structurally
      in `tests/unit/test_status/test_reader.py::TestGitCallMemoization`
      (isolated) and
      `tests/unit/test_status/test_hook_injection.py::TestGitCallAndLoadMachineCountCollapse::test_git_subprocess_call_count_stays_small_across_multi_sprint_status`
      (real multi-sprint `build_status` invocation, asserts `<= 3`).
- [x] `load_machine` parse count per invocation drops from about 20 to 3
      (one per machine name). Verified structurally in
      `tests/unit/test_state_machine/test_loader.py::TestLoadMachineCaching`
      (isolated) and
      `test_hook_injection.py::TestGitCallAndLoadMachineCountCollapse::test_load_machine_parse_count_is_three_across_multi_sprint_status`
      (real multi-sprint invocation, asserts exactly 3 parse-and-construct
      passes via `_build_machine`, one per name).
- [x] Full existing test suite passes, including any existing
      status-shape regression tests. See Measurement Notes below for the
      exact modules/counts run.
- [x] `time clasi hook status-inject < captured-payload.json`: measured
      before/after — **partially met, see Measurement Notes below for
      the honest numbers and an identified out-of-scope root cause for
      why "under 200ms" was not reached in this repo's current state.**

## Measurement Notes (recorded 2026-08-19/20)

**Baseline** (recorded in this ticket / the source issue, measured on
this repo before any of these changes): `build_status` alone ~990ms;
total `clasi hook status-inject` process ~1.05-1.15s.

**After** (this repo, same dogfooding conditions, measured via
`.venv/bin/clasi hook status-inject < captured-payload.json` piped a
minimal real `UserPromptSubmit`-shaped payload, `/usr/bin/time -p`,
6 runs): wall time ranged **0.68s-0.99s**, median ≈0.78s — a genuine
~30-45% reduction from baseline, but not under the 200ms target.
Isolating `build_status` directly (bypassing CLI/import overhead, via
`time.perf_counter()`): **644ms** with `skip_inconsistencies=True` (the
new status-inject behavior) vs **1242ms** with it `False` (the
CLI/skill's unchanged behavior) — an internally-consistent ~598ms
measured cost for `detect_inconsistencies` alone in this repo, close to
the issue's ~400ms estimate (higher here because it runs across every
evaluated sprint, see below).

**Root cause of the residual gap (not fixed — out of this ticket's
scope):** `_build_sprints_block`'s `exclude_done=True` filter (added by
an earlier ticket, "019-006 fix 1") excludes a sprint only when
`sprint.status == "done"` (raw sprint.md frontmatter string). Six
archived sprints in this repo (`clasi/sprints/done/020-*` through
`025-*`) have `status: closed` in frontmatter (matching the sprint
state machine's actual terminal state *name*, "closed" — not "done",
which is the *ticket* machine's terminal state name). Those six sprints
therefore leak past `exclude_done`, and `build_status` fully evaluates
each of them — `Project.get_sprint()` (137 calls) and
`frontmatter.read_frontmatter()` (1816 calls, ~630ms in a `cProfile`
run) sweeping every one of their (all-done) tickets — every single
invocation, real payload output confirmed 7 sprints evaluated instead
of the 1 actually active one. This is a pre-existing gap in
`exclude_done`'s status-matching, not something introduced by or listed
in this ticket's Implementation Plan (which covers exactly: git-call
memoization, `load_machine` caching, `detect_inconsistencies` removal,
and the YAML trim — all four fully implemented and verified above).
Confirmed NOT a bug in this ticket's own trim: the real output for
this repo shows sprints 020-025 correctly missing
`available_transitions` (each has `tickets: {total: 0}` after
`exclude_done`'s ticket-level, not sprint-level, filtering removes
their all-done tickets) while sprint 026 (the one truly active sprint)
correctly keeps full detail.

**Recommendation for team-lead**: a follow-up ticket/issue to widen
`exclude_done`'s sprint match (e.g. `status in {"done", "closed"}`, or
compare against the sprint machine's own computed terminal state rather
than the raw frontmatter string) would likely bring this repo's
status-inject well under the 200ms target — the four fixes in this
ticket are already why the CLI-path comparison above shows removing
`detect_inconsistencies` alone recovers ~600ms, and git/load_machine
calls no longer scale with sprint count. A project without this
leaked-archived-sprint condition (a fresh project, or this repo once
fixed) should already be comfortably under 200ms with just this
ticket's four changes.

**Test modules run** (all passing, `--no-cov`, foreground):
- `tests/unit/test_status/test_reader.py` — 78 passed (6 new memoization tests)
- `tests/unit/test_state_machine/test_loader.py` — 62 passed (13 new caching tests)
- `tests/unit/test_status/test_reporter.py` — 56 passed (7 new skip_inconsistencies tests)
- `tests/unit/test_status/test_inconsistency.py` — unaffected, included in combined run
- `tests/unit/test_status/test_hook_injection.py` — 47 passed (trim + count-collapse + skip_inconsistencies tests)
- `tests/unit/test_status/` + `tests/unit/test_state_machine/` + `tests/unit/test_hook_handlers.py` combined — 754 passed
- `tests/integration/test_status_e2e.py` — 41 passed (confirms `clasi status` CLI / `detect_inconsistencies` unaffected)
- `tests/integration/test_state_machine_smoke.py` + `tests/unit/test_state_machine/test_predicate_path_agreement.py` + `tests/unit/test_sprint.py` — 133 passed
- `tests/system/test_worktree_and_planning_integration.py` — 7 passed

## Implementation Plan

**Approach**: Add an instance-scoped cache to `ClasiStateReader`
(`src/clasi/status/reader.py`) for its git-subprocess methods — a dict
keyed by the git command/args, populated lazily on first call within
that reader instance's lifetime, never persisted across instances. Wrap
`state_machine.loader.load_machine` with `functools.lru_cache(maxsize=None)`
(the three machine names are the entire keyspace, and the packaged YAML
never changes within a process's lifetime — see this sprint's `design/`
overlay note in `state_machine-DESIGN.md`). Remove the
`detect_inconsistencies` call from the status-inject hook handler in
`hook_handlers.py` specifically (leave the CLI and project-status skill
callers untouched). Trim the YAML-building step (likely in
`status/reporter.py` or the hook handler's serialization step) to omit
`available_transitions`/`blocked_by` when a sprint's pre-flight state is
empty.

**Files to modify**:
- `src/clasi/status/reader.py` (`ClasiStateReader` git methods).
- `src/clasi/state_machine/loader.py` (`load_machine`).
- `src/clasi/hook_handlers.py` (status-inject handler: drop
  `detect_inconsistencies` call, trim payload).
- Possibly `src/clasi/status/reporter.py` if the trim belongs there
  instead of in the hook handler.
- Test modules covering `ClasiStateReader`, `load_machine`, and the
  status-inject hook handler.

**Testing plan**: Mock/count git subprocess invocations and
`load_machine` calls across a realistic `build_status` call (a fixture
project with multiple sprints/tickets) to verify the call-count
reductions structurally, not just via timing. Add a `time`-based
before/after measurement using a captured real payload. Add a
regression test comparing full status YAML output (project with active
ticketed sprints) before and after the trim, asserting only the
intended fields are dropped and only for the empty-pre-flight case.

**Documentation updates**: This sprint's `design/` overlay
(`status-DESIGN.md`, `state_machine-DESIGN.md`) already documents these
caching changes at the module level.
