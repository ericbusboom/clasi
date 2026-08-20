---
id: '003'
title: Collapse status-inject's residual git-subprocess spawns and/or hook-process
  startup imports to close the sub-200ms gap
status: in-progress
use-cases:
- SUC-003
depends-on: []
github-issue: ''
issue: status-inject-residual-latency-git-spawn-and-startup.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Collapse status-inject's residual git-subprocess spawns and/or hook-process startup imports to close the sub-200ms gap

## Description

Sprint 026 cut `status-inject`'s per-prompt latency from about
1,050-1,150ms to a median 238.4ms (ticket 007, after ticket 003's
git-call memoization and `load_machine` caching plus 007's own
terminal-sprint sweep exclusion) — a genuine 54%+ reduction, but still
above the sprint's original under-200ms success criterion. Both
tickets' own Measurement Notes (in
`clasi/sprints/done/026-hook-performance-and-guard-reliability/tickets/done/003-*.md`
and `007-*.md`) name the residual cost explicitly and rule out further
gains from anything in their own scope: it is **real OS-level git
subprocess spawn overhead** (2-3 surviving `subprocess.run` calls, each
about 20-30ms of process-creation cost that no in-process caching
removes) plus **hook-process/import startup** (the `click` CLI import
chain `cli.py` pays on every `clasi hook` invocation, plus one-time
`load_machine` YAML-parse cost on first use). Neither ticket's
Implementation Plan touched either of these — 003 was scoped to
call-count reduction, 007 to the terminal-sprint filter.

This ticket is **measurement-driven, not solution-prescribed**: profile
first, then apply whichever combination of the candidate directions
below actually moves the number, and report honest before/after
numbers either way (matching 003/007's own documented discipline — see
this sprint's Design Rationale for why the sprint plan deliberately
does not pre-select one technique).

**Key source locations verified during sprint planning**:

- `src/clasi/status/reader.py`, lines 88-225 — `ClasiStateReader`.
  Specifically:
  - Lines 88-104: `_run_git(*args)`, the per-instance memoization helper
    added by 026/ticket 003. Caches by argument tuple, but each
    distinct tuple still triggers exactly one real `subprocess.run`.
  - Lines 156-171: `git_branch()` → `self._run_git("branch",
    "--show-current")`.
  - Lines 173-198: `default_branch()` → `self._run_git("symbolic-ref",
    "refs/remotes/origin/HEAD")`, falling back to `"master"`.
  - Lines 200-225: `branch_merged(sprint_id)` → calls
    `self.sprint_branch(sprint_id)` (frontmatter read, not git),
    `self.default_branch()` (cached if already called), then
    `self._run_git("branch", "--merged", default)`.
  - These three distinct argument tuples are exactly the 2-3 real
    subprocess spawns 007's Measurement Notes attribute the residual
    latency to. Candidate directions named in the source issue: read
    `.git/HEAD` and refs directly (avoids spawning `git` at all for
    branch-name resolution) and/or collapse the remaining calls into a
    single batched plumbing invocation (e.g. `git for-each-ref`).
    Whichever is chosen, `StateReader`'s public method signatures
    (`git_branch() -> str`, `default_branch() -> str`,
    `branch_merged(sprint_id: str) -> bool`) must not change — this is
    an internal implementation change only (see sprint.md Architecture,
    "Impact on Existing Components").
- `src/clasi/cli.py` — the `click` CLI import chain. `cli.py` imports
  `click` at module level (line 24) and is the entry point
  (`pyproject.toml`'s `[project.scripts]`: `clasi = "clasi.cli:cli"`),
  so every `clasi hook ...` invocation pays click's full group-parsing
  import cost before `handle_hook` (imported lazily inside the `hook`
  command body, confirmed already lazy) ever runs. Candidate direction:
  audit remaining eager imports on the `clasi hook` path; consider
  whether a minimal dispatch entrypoint that bypasses full click-group
  parsing for hook events specifically is warranted, versus further
  lazy-import trimming within the existing structure. Profile before
  choosing — this may turn out to be a smaller contributor than the git
  spawns, per 007's own experience of a plausible-looking fix not being
  where the time actually was.
- Also named by the source issue as a possible contributor (not
  confirmed by this sprint's planning-time source read, worth a
  profiling pass): the `.clasi/oop`/StateDB bypass check
  (`_oop_active`/`_oop_db_record` in `hook_handlers.py`) that opens the
  StateDB connection before `build_status` is even called on the
  status-inject path.

## Acceptance Criteria

Per the issue's own Verification section, plus this sprint's Success
Criteria and Test Strategy:

- [ ] Before/after wall-time numbers captured using the same
      captured-payload method as sprint 026 tickets 003/007:
      `time clasi hook status-inject < captured-payload.json` (or the
      `subprocess.run` + `time.perf_counter()` variant 007 used for
      tighter resolution), same machine/session, no concurrent load,
      n>=12 runs reported both before and after.
- [ ] Median wall time after this ticket's fix is **under 200ms** on
      this repo. If not fully met, report the honest numbers and the
      identified root cause for the remaining gap (matching 003/007's
      own "partially met" precedent) rather than omitting the miss —
      this sprint's Design Rationale explicitly accepts that outcome as
      long as the evidence is honest.
- [ ] Surviving git-subprocess call count is asserted structurally
      (debug counter or mock call-count assertion on `subprocess.run`),
      not wall-clock variance alone — consistent with 003's and 007's
      own call-count assertion pattern
      (`tests/unit/test_status/test_reader.py`,
      `tests/unit/test_status/test_hook_injection.py`).
- [ ] If the fix touches hook-process import cost: an import-count or
      import-time assertion (e.g. asserting a specific module is not
      imported eagerly, or a measured import-time delta) backs the
      claimed reduction, following the same structural-evidence
      standard as the call-count assertion above.
- [ ] No behavior change to status content — full status YAML output
      for a project with active ticketed sprints is byte-identical
      before/after (existing status-shape regression tests pass
      unmodified).
- [ ] No behavior change to `clasi status` CLI output or hook exit
      semantics — `exclude_done=False` path (used by the CLI) is
      unaffected by any change scoped to the `status-inject` hook path.
- [ ] `StateReader`'s public method signatures are unchanged.

## Testing

- **Existing tests to run**: `tests/unit/test_status/test_reader.py`,
  `tests/unit/test_status/test_hook_injection.py`,
  `tests/unit/test_status/test_reporter.py`,
  `tests/integration/test_status_e2e.py` (confirms `clasi status` CLI /
  `exclude_done=False` path unaffected). Run these scoped modules only,
  foreground, per the programmer agent's test discipline — no full-suite
  or background runs during this ticket, matching the precedent 003 and
  007 both documented explicitly in their own Measurement Notes.
- **New tests to write**:
  - A call-count assertion test for whichever git-spawn-collapse
    technique is chosen (mock/count `subprocess.run` invocations across
    a realistic `build_status` call).
  - If import-trimming is part of the fix: an import-assertion test
    (e.g. `sys.modules` check or import-time measurement) proving the
    trimmed import no longer happens eagerly on the hot path.
  - A before/after timing comparison recorded in this ticket's
    Measurement Notes (following 003/007's documented format exactly —
    baseline, after, root-cause-of-any-residual-gap), even if the
    result is a partial improvement rather than a full pass under
    200ms.
- **Verification command**: run the specific new/modified test modules
  directly (e.g. `uv run pytest tests/unit/test_status/test_reader.py`),
  not the full suite.
