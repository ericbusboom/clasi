---
id: 029
title: Fail closed and resolve roots
status: roadmap
branch: sprint/029-fail-closed-and-resolve-roots
worktree: false
use-cases: []
issues:
- guard-fail-closed-exception-boundary.md
- get-project-has-no-upward-root-discovery.md
- state-db-reads-stop-creating-databases.md
- root-anchored-git-and-artifact-paths.md
- atomic-line-anchored-frontmatter-io.md
- staleness-detect-same-version-drift.md
- hook-payload-typed-ingress-and-replay-corpus.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 029: Fail closed and resolve roots

## Goals

No guard failure is ever a silent allow, and nothing in the hook or
tools layer depends on the process's working directory. This is Phase
1 of the three-sprint reliability arc from the comprehensive review
(`docs/reviews/2026-08-reliability/00-review.md`, Part 5): sprint 028
built the instrumented E2E and started capturing a real deny-payload
corpus; this sprint spends that instrument on the two highest-leverage
root causes (RC-2 "failure is silent," RC-3 "everything trusts cwd")
before Phase 2 touches state vocabulary. The review estimates the
headline fixes at under 200 lines total across the five changes below
— small, surgical diffs, not a rewrite.

## Problem

Per the review's C1/C2/C6 findings (and the RC-2/RC-3 root-cause
sections): the Claude Code harness only blocks a tool call on hook
exit code 2, so any crash, timeout, or spawn failure inside a CLASI
guard is an unlogged **allow** — `hooks.log` already shows 876 events
from a stretch when role-guard ran fail-open unnoticed. Separately,
`get_project()` is `Project(Path.cwd())` with no upward search for
`.clasi/`, so a hook fired from a subdirectory resolves every path
against the wrong root; because every DB **read** auto-creates a
fresh schema'd database at whatever path it's handed, the wrong root
gets a phantom DB where the OOP flag is off, the lock is invisible,
and the agent tier is unset — guards fail open with benign-looking
logs. The same cwd trust runs through the tools layer (most git
subprocesses spawn with no `cwd=`, relative artifact paths resolve
against the server process's directory) and through staleness
detection (`check_staleness` cannot see same-version drift — the exact
gap noted in project memory). Frontmatter parsing is not line-anchored
and writes are not atomic, so a crash mid-write corrupts a sprint or
ticket file and `list_sprints` silently drops it. None of this is
theoretical: sprint 028's guard-decision-trail work starts capturing
real deny payloads specifically so this sprint's fixes can be tested
against genuine data instead of hand-written fixtures.

## Solution

Seven phase-1 issues, ordered so the exception boundary and root
discovery (the two structural fixes) land before the narrower
path-hygiene and replay work that depends on them being correct:

1. `guard-fail-closed-exception-boundary.md` — exception boundary in
   `handle_hook`: any guard crash becomes exit 2 plus a `guard-crash`
   log line, instead of falling through to an allow.
2. `get-project-has-no-upward-root-discovery.md` — `get_project()`
   walks upward via `_find_project_root` to find `.clasi/`, so a hook
   fired from any subdirectory resolves the correct project root.
3. `state-db-reads-stop-creating-databases.md` — DB reads stop
   creating databases as a side effect; SQLite opens with a short
   `timeout=1` so contention fails fast and visibly instead of eating
   a guard's latency budget.
4. `root-anchored-git-and-artifact-paths.md` — one `run_git(args,
   cwd=project.root)` helper used across the tools layer and
   `sprint.py`, plus root-anchored artifact path resolution; commits
   use explicit pathspecs instead of bare `git commit -m`.
5. `atomic-line-anchored-frontmatter-io.md` — frontmatter reads become
   line-anchored and writes become atomic (write-temp-then-rename), so
   a crash mid-write can no longer corrupt a sprint or ticket file.
6. `staleness-detect-same-version-drift.md` — an mtime-vs-import-time
   check in `check_staleness` closes the same-version-drift gap (a
   long-lived MCP process can hold pre-fix code in memory with no
   version-string change to detect it by).
7. `hook-payload-typed-ingress-and-replay-corpus.md` — replay the deny
   payloads sprint 028's guard-decision-trail capture starts writing,
   as tests that assert the deny path fires on real, previously-seen
   malformed payloads rather than synthetic ones.

## Success Criteria

- A guard crash produces exit 2 and a `guard-crash` log line — no
  crash path returns an allow.
- `get_project()` resolves the correct `.clasi/` root when invoked
  from a subdirectory of the project.
- A DB read against a path with no existing database does not create
  one; only an explicit write path does.
- Git subprocesses in the tools layer and `sprint.py` run with
  `cwd=project.root`; artifact paths resolve against the project root
  regardless of the server process's own working directory.
- A crash mid-frontmatter-write leaves the prior valid content intact
  (no partial-write corruption), and frontmatter parsing tolerates
  content that isn't perfectly formatted.
- `check_staleness` flags a same-version drift case (source changed,
  version string unchanged) that it currently misses.
- At least one replay test asserts a deny decision against a real
  payload captured by sprint 028's corpus.
- The E2E guard-probe, subdirectory-cwd, and stale-server scenarios
  all pass under the instrumented run from sprint 028.
- The diff stays small and surgical — the review's under-200-line
  estimate for the headline fixes is a useful sanity check, not a hard
  cap to engineer toward.

## Scope

### In Scope

The seven phase-1 issues listed under Solution above — the guard
exception boundary, upward root discovery, DB-read side-effect
removal, root-anchored git/artifact paths, atomic frontmatter I/O,
same-version staleness detection, and the deny-payload replay corpus.

### Out of Scope

- Phase 2 of the arc (single sprint-stage vocabulary, resumable
  `close_sprint`, the impossible-predicate fixes) — third sprint,
  planned separately.
- Phase 3 (gate-order fix, tier-0 relaxation, doc/process
  consolidation) and Phases 4-5 (deletion, decomposition, test-suite
  activation) — later, per the review's Part 5 sequencing; this sprint
  does not touch process docs or delete dead code.
- Any change to what a guard's *policy* allows or denies — this
  sprint changes what happens when a guard **fails**, not the
  decisions a healthy guard makes.
- The OpenRouter E2E auth path — stays parked in
  `clasi/issues/later/claude-cli-rejects-models-through-openrouter-redirect-in-e2e.md`
  per the review's Part 6 decision.

## Test Strategy

(To be detailed when this sprint is promoted to Detail Mode. At a
minimum: unit tests for the `handle_hook` exception boundary and
`_find_project_root` walking from nested subdirectories; a DB-read
test asserting no file is created at a fresh path; replay tests over
sprint 028's captured deny-payload corpus. Primary validation is the
instrumented E2E from sprint 028: guard-probe scenario — a malformed
payload denies rather than allows; subdirectory-cwd scenario — a hook
fired from a subdirectory resolves the real project root; stale-server
scenario — the new mtime drift signal trips.)

## Architecture

(Architecture for this sprint's change, sized to the change — a
one-paragraph note for a trivial sprint, a fuller write-up with
component/data-model detail for a substantial one. May read "N/A —
trivial" when the change has no architectural impact.)

### Architecture Overview

(High-level structure and component relationships, if applicable.)

### Design Rationale

(Significant decisions with alternatives considered and reasoning, if
applicable.)

### Migration Concerns

(Data migration, backward compatibility, deployment sequencing — or
"None" if not applicable.)

## Use Cases

(Use cases sized to the change — may read "N/A — trivial" for small
sprints that don't warrant new or updated use cases.)

### SUC-001: (Title)
Parent: UC-XXX

- **Actor**: (Who)
- **Preconditions**: (What must be true before)
- **Main Flow**:
  1. (Step)
- **Postconditions**: (What is true after)
- **Acceptance Criteria**:
  - [ ] (Criterion)

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [ ] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|

Tickets execute serially in the order listed.
