---
id: '003'
title: Collapse status-inject's residual git-subprocess spawns and/or hook-process
  startup imports to close the sub-200ms gap
status: done
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

- [x] Before/after wall-time numbers captured using the same
      captured-payload method as sprint 026 tickets 003/007:
      `time clasi hook status-inject < captured-payload.json` (or the
      `subprocess.run` + `time.perf_counter()` variant 007 used for
      tighter resolution), same machine/session, no concurrent load,
      n>=12 runs reported both before and after. See Measurement Notes.
- [x] Median wall time after this ticket's fix is **under 200ms** on
      this repo. **Fully met**: median dropped from 253.0ms (baseline,
      n=20) to 155.6-168.5ms across two independent after-measurement
      sessions (n=20 each) — see Measurement Notes for both runs and
      the root-cause breakdown of where the time actually went (it was
      NOT primarily the git spawns the ticket's own text emphasized
      most — see below).
- [x] Surviving git-subprocess call count is asserted structurally
      (debug counter or mock call-count assertion on `subprocess.run`),
      not wall-clock variance alone — consistent with 003's and 007's
      own call-count assertion pattern
      (`tests/unit/test_status/test_reader.py`,
      `tests/unit/test_status/test_hook_injection.py`). New:
      `TestGitBranchFastPath`, `TestDefaultBranchFastPath` (reader),
      `TestGitSpawnCollapseInRealRepo` (hook injection, real git repo
      fixture) — all assert 0 real `subprocess.run` calls where the
      fast path applies.
- [x] If the fix touches hook-process import cost: an import-count or
      import-time assertion (e.g. asserting a specific module is not
      imported eagerly, or a measured import-time delta) backs the
      claimed reduction, following the same structural-evidence
      standard as the call-count assertion above. New:
      `TestSchemasNotImportedOnStatusInjectHotPath` — asserts `pydantic`
      and `clasi.schemas.graph`/`.models` are not in `sys.modules` after
      a real `handle_status_inject` call.
- [x] No behavior change to status content — full status YAML output
      for a project with active ticketed sprints is byte-identical
      before/after (existing status-shape regression tests pass
      unmodified). Verified: `test_reporter.py` (56 tests) +
      `test_status_e2e.py` (45 tests) pass unmodified; new
      `test_attached_head_matches_subprocess_result` directly compares
      the fast path's answer against a real `git branch --show-current`
      invocation on the same repo state.
- [x] No behavior change to `clasi status` CLI output or hook exit
      semantics — `exclude_done=False` path (used by the CLI) is
      unaffected by any change scoped to the `status-inject` hook path.
      Verified: `clasi status` run manually post-change (exit 0, valid
      YAML); `test_status_e2e.py`'s CLI-path tests pass unmodified; this
      ticket's changes touch only `ClasiStateReader.git_branch`/
      `default_branch` (called identically from both paths) and
      import-timing internals of `state_db_class`/`clasi.schemas`, never
      `exclude_done`-related logic in `reporter.py`.
- [x] `StateReader`'s public method signatures are unchanged.
      `git_branch() -> str`, `default_branch() -> str`,
      `branch_merged(sprint_id: str) -> bool` are untouched; only new
      private helpers (`_git_dir`, `_read_ref_file`, `_git_branch_fast`,
      `_default_branch_fast`) were added.

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

## Measurement Notes (recorded 2026-08-19/20)

**Method**: `subprocess.run` + `time.perf_counter()` (007's tighter-
resolution variant), invoking `.venv/bin/clasi hook status-inject` with
the same captured `UserPromptSubmit`-shaped payload piped via stdin each
time, same machine/session, no other load intentionally running
concurrently.

**Baseline** (this repo, current HEAD before this ticket's changes,
n=20): range 228.4-328.7ms, median **253.0ms**, mean 263.6ms. (Slightly
above 007's own last-recorded 238.4ms median — consistent normal
session-to-session variance on the same machine, not a regression: no
code changed between 007 landing and this ticket starting.)

**Profiling before implementing** (`cProfile` over an in-process
`handle_status_inject` call, avoiding CLI-launch noise so the
breakdown is legible): total profiled time 416ms, of which:
- `hook_handlers._oop_active` → `_oop_db_record` → `from
  clasi.state_db_class import StateDB`: **137ms**, almost entirely a
  one-time import cascade (`clasi.schemas` → `clasi.schemas.graph` /
  `clasi.schemas.models` → `pydantic`, ~115ms of it) triggered by
  `state_db_class.py`'s **module-level** `PHASES = ArtifactGraph(...)`
  computation — needed only by `advance_phase`'s write path, never by
  a read-only status build, but paid on every import of the module.
- `ClasiStateReader._run_git` → `subprocess.run`: **131ms** across 2
  real spawns (`git branch --show-current`, `git symbolic-ref
  refs/remotes/origin/HEAD`) — `branch_merged`'s `--merged` spawn did
  not fire for this repo's current sprint state (`executing`; that
  predicate only evaluates near sprint close).
- Everything else (state-machine evaluation, YAML/frontmatter
  reads, `narrow_status`, formatting): the remaining ~150ms.

This is the sprint's third confirmed "the assumed bottleneck wasn't
the full story" finding (007 had one too, re: `exclude_done`): the
ticket's own text emphasized the git spawns as the headline candidate,
but profiling showed the `clasi.schemas`/pydantic import chain
(triggered by the **OOP bypass check**, which every hook invocation
pays *before* `build_status` even runs) was actually the single
largest contributor — bigger than both surviving git spawns combined.
Further investigation found the SAME import chain is also triggered
independently by `state_machine.loader.load_machine`'s
`importlib.resources.files("clasi.schemas")` resource-path lookup
(needed on every `build_status` call, regardless of the OOP check) —
because `clasi/schemas/__init__.py` itself eagerly imported
`.graph`/`.models` at package-import time for its own re-exports. That
meant fixing only `state_db_class.py`'s PHASES eagerness would have
saved nothing end-to-end (whichever caller runs first pays the cost;
`load_machine` would have paid it moments later regardless). Confirmed
via `python -X importtime -c "from clasi.state_machine.loader import
load_machine; load_machine('project')"` showing `pydantic` fully
imported from that call alone, with no `state_db_class` involved at
all.

**Fixes implemented** (both required together — see above):
1. `clasi/schemas/__init__.py`: `ArtifactGraph`, `SchemaError`,
   `GateSpec`, `ArtifactSpec`, `WorkflowSchema` are now resolved lazily
   via a PEP 562 module `__getattr__`, cached on first real access.
   Merely importing the `clasi.schemas` package (e.g. for a resource
   path lookup) no longer cascades into `.graph`/`.models`/pydantic.
2. `state_db_class.py`: `PHASES` is now computed lazily (also via
   module `__getattr__`, backed by a `_compute_phases()` cache), moving
   its own `from clasi.schemas import loader` / `from
   clasi.schemas.graph import ArtifactGraph` imports out of module-load
   time and into first real access (`advance_phase`, and
   `tools/artifact_tools.py`'s phase-index checks). `state_db.py`'s
   wrapper re-export of `PHASES` was made lazy the same way, so it
   doesn't defeat the class-level fix for its own callers.
3. `status/reader.py`: `git_branch()` and `default_branch()` each try a
   direct loose-ref-file read first (`.git/HEAD`,
   `.git/refs/remotes/origin/HEAD`) — resolving the real git directory
   through `.git`-as-directory or `.git`-as-worktree-pointer-file, both
   handled — and fall back to the exact same `_run_git`-memoized
   subprocess call used before whenever the fast path can't confidently
   answer (missing file, detached-HEAD-but-unrecognized content, no
   remote configured, non-git directory). `branch_merged` is
   deliberately unchanged — a real ancestry/merge-base check, not a
   single ref read; reimplementing it from raw git internals would risk
   the exact "keep behavior identical" divergence this ticket must
   avoid, for a call this repo's current sprint state doesn't even
   invoke.

**Structural verification** (real repo, sprint 027's own current git
state, `subprocess.run` patched to count real spawns): **0** git
subprocess spawns and `pydantic`/`clasi.schemas.graph`/`.models`
absent from `sys.modules` after a real `handle_status_inject` call —
down from 2 real git spawns and the full pydantic import chain before.
`clasi.schemas` (the package) is still imported (`load_machine` needs
it for the resource path), but that import is now cheap since it no
longer cascades into its submodules.

**After** (same method as baseline, two independent sessions, n=20
each):
- Session 1: range 143.1-345.4ms, median **168.5ms**, mean 182.1ms.
- Session 2 (no concurrent background test run this time): range
  140.4-251.1ms, median **155.6ms**, mean 165.9ms.
- **Target met**: both sessions' medians (155.6ms, 168.5ms) are
  comfortably under the 200ms threshold — a 33-38% reduction from the
  253.0ms baseline. A few individual runs in each session (up to
  ~345ms) are outliers consistent with normal OS scheduling noise on a
  shared dev machine, not a regression in the typical case the median
  reports.

**End-to-end hook verification** (per this ticket's "Caution: LIVE
hook" instruction, run after implementing, before committing):
`clasi hook role-guard` (Read tool payload) → exit 0; `clasi hook
mcp-guard` (team-lead calling an MCP tool directly) → exit 2 with the
expected role-violation message (guard still fires correctly); `clasi
status` → exit 0, valid YAML. All three dispatch and evaluate
correctly through the same `cli.py` → `hook_handlers.py` /
`state_db_class.py` code this ticket touched.

**Test modules run** (all passing, `--no-cov`, foreground):
- `tests/unit/test_status/test_reader.py` — 86 passed (7 new:
  `TestGitBranchFastPath` x5, `TestDefaultBranchFastPath` x2, plus 3
  existing `TestGitCallMemoization` assertions updated to reflect the
  new, lower, real spawn counts for this fixture's specific shape)
- `tests/unit/test_status/test_hook_injection.py` — 53 passed (4 new:
  `TestGitSpawnCollapseInRealRepo` x3,
  `TestSchemasNotImportedOnStatusInjectHotPath` x1)
- `tests/unit/test_status/test_reporter.py` +
  `tests/integration/test_status_e2e.py` — 101 passed, unmodified
  (confirms byte-identical status content and the CLI's
  `exclude_done=False` path)
- `tests/unit/test_hook_handlers.py` + `tests/unit/test_cli.py` — 261
  passed, unmodified
- `tests/unit/test_state_db.py` + `tests/unit/test_state_db_class.py`
  — 97 passed, unmodified (direct coverage of the lazy-`PHASES` files)
- `tests/clasi/schemas/` — 62 passed, unmodified (direct coverage of
  the lazy-`__init__.py` file)

**Scope note**: the ticket's second candidate direction (trimming
`cli.py`'s `click` import chain, measured at ~16ms via `python -X
importtime -c "import clasi.cli"`) was profiled but not touched — with
both fixes above, the median is already 31-44ms under the 200ms target,
and click's own cost is an order of magnitude smaller than either lever
actually implemented. Per the ticket's own "profile first... apply
whichever combination... actually moves the number" instruction, this
was left alone rather than risking the "internal fast-path dispatch"
restructuring for headroom the numbers show isn't needed.
