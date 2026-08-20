---
id: '027'
title: 'Hook lifecycle aftercare: retired events, clean bump commits, sub-200ms status'
status: planning-docs
branch: sprint/027-hook-lifecycle-aftercare-retired-events-clean-bump-commits-sub-200ms-status
worktree: false
use-cases: []
issues:
- removed-commit-check-subcommand-breaks-stale-hook-registrations.md
- close-sprint-version-bump-commits-unrelated-untracked-files.md
- status-inject-residual-latency-git-spawn-and-startup.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 027: Hook lifecycle aftercare: retired events, clean bump commits, sub-200ms status

## Goals

Close out three field-report/measurement follow-ups from sprint 026's
hook-performance-and-guard-reliability work, each already fully diagnosed
in its own issue file:

1. Stop `clasi hook` hard-erroring on retired event names
   (`commit-check`, `task-created`, `task-completed`) so stale
   pre-026 hook registrations degrade gracefully instead of breaking
   every `Bash` call in the affected session.
2. Stop `close_sprint`'s version-bump commit from sweeping unrelated
   untracked files into master.
3. Close the remaining gap between status-inject's post-026 measured
   238.4ms median and its original under-200ms success criterion.

## Problem

Sprint 026 removed dead hook handlers, tightened close_sprint's
staging in one place but not another, and got status-inject most but
not all of the way to its latency target. Each fix landed correctly
for what it covered; each left a documented, narrow gap:

- **Retired events**: `clasi hook <event>` treats any name outside its
  routing table as a hard CLI error. Hook registrations are
  snapshotted at session start (or baked into a pre-026 `clasi init`
  in a consumer project) and upgrade on a different schedule than the
  CLI, so a removed event name now breaks sessions that never touched
  the CLASI upgrade themselves.
- **Bump commit staging**: the version-bump step in
  `_close_sprint_full` stages with `git add -A` instead of the
  specific file(s) it just wrote, so anything else sitting untracked
  or modified in the working tree rides along into a commit whose
  message claims to be a version bump.
- **status-inject latency**: tickets 003 and 007 removed the
  scaling-with-sprint-count costs (redundant git calls, repeated YAML
  parsing, inline diagnostics, terminal-sprint leakage) and got this
  repo from about 1.1s to a 238.4ms median — a real fix, but their own
  Measurement Notes identify the residual cost as real OS-level git
  subprocess spawn overhead and hook-process/import startup, neither
  of which either ticket's scope touched.

## Solution

Three independent, narrowly-scoped fixes, each confined to the module
its own issue already traced the cause to:

1. `clasi hook` gains a small **retired-event allowlist**
   (`hook_handlers.handle_hook`'s dispatcher, plus `cli.py`'s argument
   validation so the retired name isn't rejected before it ever
   reaches the dispatcher) that no-ops with exit 0, a stderr
   deprecation line, and a `hooks.log` entry — while any name outside
   both the live routing table and this allowlist still hard-errors,
   so a typo in a fresh registration still surfaces loudly.
2. `_close_sprint_full`'s version-bump step stages **only the file(s)
   it just wrote** (the detected version file), matching the
   already-correct scoped-staging pattern its own Step 5b already uses
   for `.clasi.db` two steps later in the same function.
3. Collapse the git-subprocess spawns that survive ticket 003's
   memoization (`ClasiStateReader.git_branch` / `default_branch` /
   `branch_merged`, 2-3 real `subprocess.run` calls per invocation)
   and/or trim `clasi hook`'s process-startup import cost, guided by
   the same captured-payload before/after measurement method tickets
   003 and 007 used. The exact technique is a ticket-time,
   measurement-driven decision (see Design Rationale) — this sprint
   does not pre-select one.

## Success Criteria

- A session/fixture carrying a pre-026 `.claude/settings.json` (with
  the `commit-check` PostToolUse/Bash registration) runs `Bash` calls
  cleanly against post-fix `clasi`: the hook exits 0, no error
  surfaced, and a genuinely unknown event name still exits non-zero.
- A fixture repo with an unrelated untracked file present through a
  full `close_sprint` run: the file is still untracked afterward and
  absent from every commit `close_sprint` created.
- `time clasi hook status-inject < captured-payload.json` in this repo
  is under 200ms median (n>=12), with call-count or import-count
  evidence (not wall-clock alone) backing the claimed reduction, and
  no change to status content, `clasi status` CLI output, or hook exit
  semantics.

## Scope

### In Scope

- Retired-event allowlist in `clasi hook` (dispatcher + CLI argument
  handling) covering `commit-check`, `task-created`, `task-completed`,
  and their documented alias forms.
- Optional: a stale-hook-registration detection nudge (e.g. `clasi
  init --check` or the existing staleness check) recommending `clasi
  init` refresh — secondary to the no-op fix itself; scoped at ticket
  time against remaining budget (see Open Questions).
- Explicit file staging for `_close_sprint_full`'s version-bump commit.
- Further git-subprocess-spawn collapse and/or hook-process import
  trimming on the `status-inject` path, with before/after measurement.
- Regression tests for every fix, including both the allow/no-op path
  and the still-errors/unchanged path (guard changes never ship with
  only the happy path tested).

### Out of Scope

- Any other latency work outside `status-inject` (e.g. `role-guard`,
  `mcp-guard` timing) — not measured as a problem by issue 3.
- Redesigning the hook registration/versioning model itself (e.g. a
  registration-schema version field) — the allowlist is a bridge, not
  a permanent mechanism, per the issue's own framing.
- The separate `sprint-phase-gate-order-contradicts-plan-sprint-skill-docs.md`
  and other currently-pending issues in `clasi/issues/` — out of this
  sprint's claimed scope.

## Test Strategy

Each ticket adds regression tests colocated with the module it
changes, following the existing suite's real-payload convention (the
project's own dogfooded hooks.log/session data, not only mocks):

- **Retired events**: CLI-level invocation tests with real captured
  payloads for each retired name (exit 0, deprecation line, hooks.log
  entry) and for a typo'd/unknown name (exit non-zero, unchanged).
- **Bump commit staging**: a fixture-repo test that seeds an unrelated
  untracked file, runs the close lifecycle's version-bump step, and
  asserts the file is absent from `git show --stat` on the resulting
  commit and remains untracked in `git status --porcelain`.
- **status-inject latency**: the captured-payload timing method from
  sprint 026 tickets 003/007, plus a structural call-count (or
  import-count) assertion so the improvement is verifiable without
  relying on wall-clock variance alone. Foreground-only, ticket-scoped
  test runs per the programmer agent's now-codified test discipline —
  no full-suite or background test runs during ticket execution.

## Architecture

**Substantial by module count, no diagram** — this sprint touches three
existing modules across three subsystems (`clasi-core`'s
`hook_handlers.py`/`cli.py`, `clasi.tools`'s `artifact_tools.py`, and
`clasi.status`'s `reader.py`), which crosses the 3+-modules signal for
the substantial tier. But, exactly as sprint 020's precedent for this
same shape: the three fixes are independent bugfixes/latency work
inside existing modules — no new subsystem is introduced, no new
cross-module dependency is added, no dependency direction changes, and
no data model changes. A component or dependency diagram would show
the same three pre-existing, already-unconnected modules with no new
edges between them — it would not clarify anything a reader doesn't
already get from the module list below, so it is omitted per the same
reasoned-exception the tier description allows.

### Architecture Overview

**What Changed**

1. **`hook_handlers.py` / `cli.py` (clasi-core)** — `handle_hook`'s
   dispatcher (`_ROUTING_TABLE`) gains a second, smaller lookup: a
   `_RETIRED_EVENTS` allowlist (`commit-check`, `task-created`,
   `task-completed`, and their documented alias forms) checked when an
   event name isn't in the live routing table. A retired name no-ops
   (exit 0, one stderr deprecation line, a `hooks.log` `retired-event`
   entry); anything in neither the routing table nor the allowlist
   still hard-errors exit 1, unchanged. `cli.py`'s `hook` command
   currently declares its `event` argument as `click.Choice([...])`
   listing only the live events — that Choice list has to widen (or
   the argument has to move off `click.Choice` onto a validated plain
   string) to admit retired names at all, or click itself rejects them
   with a usage error before `handle_hook` ever runs. Optionally,
   `staleness.py`/`init_command.py` gain a stale-hook-registration
   detection nudge (`clasi init --check` or the existing staleness
   check) that recommends re-running `clasi init` when installed
   `.claude/settings.json` still names events the current CLI no
   longer serves — a bridge-mechanism health signal, not a new
   subsystem.
2. **`artifact_tools.py` (clasi.tools)** — `_close_sprint_full`'s
   version-bump step (Step 5, currently `git add -A` followed by `git
   commit -m "chore: bump version to …"`) changes to stage explicitly:
   only the version file `detect_version_file`/`update_version_file`
   just wrote (and only if a version file was actually detected — no
   staging or commit attempt otherwise). This mirrors the function's
   own Step 5b three steps later, which already stages exactly
   `str(db_file)` for the `.clasi.db` follow-up commit — the fix
   brings Step 5 in line with a pattern already correct two steps
   away in the same function, not a new pattern.
3. **`reader.py` (clasi.status)**, and secondarily `hook_handlers.py`/
   `cli.py` again (clasi-core) — `ClasiStateReader`'s three
   git-subprocess-backed methods (`git_branch`, `default_branch`,
   `branch_merged`) currently memoize *within* a reader instance
   (ticket 003) but still shell out 2-3 real `subprocess.run` calls
   per `status-inject` invocation; each spawn costs about 20-30ms of
   OS process creation that no amount of in-process caching removes.
   The fix collapses these further (direct `.git/HEAD`/ref reads
   and/or a single batched plumbing call in place of 2-3 separate
   `git` invocations) and/or trims `clasi hook`'s own process-startup
   import cost (the `click` CLI import chain `cli.py` pays on every
   invocation). No new method signatures are required at the
   `StateReader` protocol level — this is an internal implementation
   change to already-existing methods.

**Why**: each fix closes a specific, already-measured or
already-reported gap from sprint 026 — a retired-registration failure
mode field-reported the day after 026 closed, a staging bug observed
at 026's own close, and a latency target 026's own Measurement Notes
document as not-fully-met with the specific residual cost named. None
of the three requires rethinking how its module fits into the rest of
the system.

**Impact on Existing Components**: Additive/corrective only. No
existing caller of `handle_hook`, `_close_sprint_full`, or
`ClasiStateReader`'s public methods changes its calling convention;
behavior changes only for the specific failure mode each issue
describes (retired event names, unrelated-file sweep, latency).

### Design Rationale

**Decision: a named retired-event allowlist, not a blanket
tolerate-unknown-names catch-all.**
*Context*: hook registrations upgrade on a different schedule than the
CLI (session snapshot, or a consumer project's stale `clasi init`).
*Alternatives considered*: (a) make `clasi hook` tolerate *any*
unrecognized event name silently — rejected, because it would also
swallow a genuine typo in a brand-new hook registration forever,
turning a loud, fixable CLI error into a silent no-op with no signal
anything is wrong; (b) require immediate re-`init` before any hook
call succeeds — rejected, there is no mechanism to force a running
session to re-init mid-session, so this would just convert the crash
into a different, still-unattended-session-breaking failure. *Why this
choice*: a small, explicit, named allowlist keeps the fix narrowly
targeted at exactly the registrations sprint 026 removed, preserves
the hard-error signal for everything else, and pairs with an optional
staleness nudge as the actual long-term fix (re-`init`), making the
no-op path a bridge rather than a permanent silent state. *Consequences*:
the allowlist needs pruning as retirements age out of realistic
installed-registration lifetimes — an accepted, bounded maintenance
cost, not a design flaw.

**Decision: explicit file staging for the bump commit, not a
broader-staging-plus-exclude-list.**
*Context*: `git add -A` swept an unrelated pre-existing untracked file
into a commit whose message claims to be a version bump.
*Alternatives considered*: (a) keep `git add -A` but maintain a
blacklist of files/patterns to exclude — rejected, an
exclude-list-of-badness is unbounded and reactive (it only grows after
the next surprising sweep); (b) fail `close_sprint` outright if any
unexpected untracked/modified file is present at bump time (one of the
issue's own proposed-fix alternatives) — considered, but adds a new
recovery-state branch to a function that already has several, for a
problem explicit staging solves without any new failure mode.
*Why this choice*: explicit allow-listing (stage exactly what this
step wrote) is the same shape as the function's own already-correct
Step 5b pattern for `.clasi.db` — no new mechanism, just consistent
application of the one already in the codebase. *Consequences*: if a
future version-bump path starts touching more than one file (e.g. a
lockfile sync target), the explicit staging list must be extended in
the same change that adds the new sync target — an easy point to miss,
worth a code comment at the staging call site.

**Decision: leave the specific latency-reduction technique open at
planning time.**
*Context*: issue 3 itself frames this as "candidate directions, pick
at planning time... measure before choosing," and tickets 003/007's
own history shows the plausible-looking fix (sprint-count scaling) was
not where 007's own residual gap turned out to live (real OS
process-spawn cost, not sprint count).
*Alternatives considered*: pre-select one technique now (e.g. mandate
`.git/HEAD` file reads) — rejected, locking in a mechanism before
profiling risks repeating 003/007's own experience of a plausible fix
that doesn't fully address the measured cost. *Why this choice*: the
ticket carries the measurement obligation (before/after wall time,
call/import-count evidence) instead of a locked mechanism, consistent
with this sprint's own Test Strategy and with 003/007's documented
discipline. *Consequences*: the programmer may need more than one
profiling pass within the ticket's session before landing a fix that
actually clears 200ms; acceptance criteria are written to require
evidence either way (see SUC-003), not just a single wall-clock
number.

### Migration Concerns

None. No data model changes; the retired-event allowlist is additive
(existing routed events and the existing hard-error path for unknown
names are both unchanged); the bump-commit staging change is
behavior-only with no schema or file-format impact; the status-inject
latency change is required to produce byte-identical status content
and unchanged hook exit semantics (see Success Criteria) — a
regression there would be a bug, not an intended migration.

### Open Questions

- **Stale-registration detection nudge (issue 1's Proposed-fix item
  2)**: the issue frames this as "consider," not mandatory. Decide at
  ticket time whether `clasi init --check` or a staleness-check
  extension fits in ticket 001's scope alongside the no-op allowlist,
  or should split into its own follow-up issue if it turns out to need
  more than a small addition. The no-op allowlist itself is the
  load-bearing fix either way.
- **Exact status-inject latency technique**: intentionally left open —
  see Design Rationale above. Ticket 003 (this sprint's numbering) owns
  the profiling and the choice between direct ref reads, a batched
  plumbing call, hook-startup import trimming, or some combination.

## Use Cases

Three sprint-level use cases, one per issue — each traces to an
existing top-level use case in `docs/design/usecases.md`; issue 1 has
no exact existing parent (no UC currently covers hook-event dispatch
mechanics), so its parent is the closest umbrella flow in which the
hook fires on every tool call.

### SUC-001: Retired hook event degrades gracefully instead of breaking the session
Parent: UC-002 — Execute TODOs Through a Full Sprint (the hook fires on
every `Bash` call within any TODO/sprint execution session; no UC
covers hook-event dispatch mechanics directly)

- **Actor**: Hook dispatcher (`clasi hook`), invoked by Claude Code or
  Codex on behalf of an agent session.
- **Preconditions**: A hook registration in `.claude/settings.json`
  (or a running session's already-loaded hook config, snapshotted at
  session start) names an event the current CLASI build no longer
  serves — `commit-check`, `task-created`, `task-completed`, or a
  documented alias.
- **Main Flow**:
  1. Claude Code/Codex fires the registered hook, invoking `clasi hook
     <retired-event>` with the real tool payload on stdin.
  2. `clasi hook` recognizes `<retired-event>` as a member of the
     retired-event allowlist rather than the live routing table.
  3. The dispatcher no-ops: writes a `retired-event` line to
     `hooks.log`, prints a single deprecation line to stderr, and
     exits 0.
  4. The triggering tool call (e.g. `Bash`) proceeds unblocked.
- **Postconditions**: The session's tool call is not blocked or
  errored by the retired registration; `hooks.log` carries a record of
  the no-op for later staleness diagnosis.
- **Acceptance Criteria**:
  - [ ] Each retired event name (`commit-check`, `task-created`,
        `task-completed`, and documented alias forms) exits 0 given a
        real captured payload on stdin, with no stderr noise beyond
        the single deprecation line.
  - [ ] A genuinely unknown (non-retired, non-routed) event name still
        exits non-zero, unchanged from today.
  - [ ] `hooks.log` gains a `retired-event`-tagged entry distinguishable
        from normal dispatch lines.

### SUC-002: close_sprint's bump commit contains only what it changed
Parent: UC-005 — Close a Completed Sprint

- **Actor**: Team Lead (via `close_sprint`), Stakeholder (owns what
  lands in their working tree at close).
- **Preconditions**: A sprint reaches close; `version_trigger`
  evaluates to "bump now"; the working tree may hold unrelated
  untracked or modified files that predate the sprint and were never
  part of any ticket's work.
- **Main Flow**:
  1. `close_sprint` computes the next version and writes it to the
     detected version file.
  2. The bump step stages only the file(s) it just wrote — never a
     blanket `git add -A` — and stages nothing if no version file was
     detected.
  3. The bump commit (`"chore: bump version to …"`) is created from
     that explicit staging set.
- **Postconditions**: Any untracked or modified file that predates the
  sprint and was not touched by CLASI's own bump step remains
  untracked/unmodified — absent from the bump commit and from every
  other commit `close_sprint` created.
- **Acceptance Criteria**:
  - [ ] A fixture repo with an unrelated untracked file present
        through a full `close_sprint` run: the file remains untracked
        afterward and appears in no commit `close_sprint` created.
  - [ ] The bump commit's changed-file list is exactly the detected
        version file (plus the `.clasi.db` file only if Step 5b's
        pre-existing, separately-scoped commit also fires) — no
        incidental inclusions.

### SUC-003: Status block injects in under 200ms
Parent: UC-013 — Check Project Status

- **Actor**: Hook dispatcher (`status-inject`, `UserPromptSubmit`),
  the Team Lead session consuming the injected block.
- **Preconditions**: A project shaped like this repo's own dogfooding
  state (at least one active ticketed sprint, several archived sprints
  under `done/`); sprint 026's prior fixes (git-call memoization,
  `load_machine` caching, `detect_inconsistencies` removal,
  terminal-sprint exclusion) are already applied on this same code
  path.
- **Main Flow**:
  1. Claude Code fires `UserPromptSubmit`, invoking `clasi hook
     status-inject` with the real payload.
  2. The hook builds and prints the status block using the
     already-optimized code path plus this sprint's further
     git-spawn-collapse and/or import-trimming fix.
  3. `time clasi hook status-inject < captured-payload.json` measures
     under 200ms median, n>=12, on this repo.
- **Postconditions**: Status content, `clasi status` CLI output, and
  hook exit semantics are byte-identical to before this sprint — only
  latency improves.
- **Acceptance Criteria**:
  - [ ] Before/after wall-time numbers captured with the same
        payload/method as sprint 026 tickets 003/007 (median under
        200ms after; n>=12).
  - [ ] Surviving git-subprocess call count and/or import count is
        asserted structurally (debug counter or mock call-count
        assertion), not wall-clock variance alone.
  - [ ] No behavior change to status content or hook exit codes —
        existing status-shape regression tests pass unmodified.

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [x] Architecture review passed — self-reviewed inline by the
      sprint-planner (substantial tier, diagram omitted with stated
      justification; see Architecture above); recorded via
      `record_gate_result(sprint_id="027", gate="architecture_review",
      result="passed")`.
- [x] Stakeholder has approved the sprint plan — approved 2026-08-20 on
      the stakeholder's standing written pre-approval ("run a new
      sprint with the last three issues ... run all the way through to
      master"); `stakeholder_approval` gate recorded by the team-lead
      (`record_gate_result(sprint_id="027", gate="stakeholder_approval",
      result="passed")`).

## Tickets

Materialized as tickets 001-003 in `tickets/`, one per linked issue,
`issue=` passed explicitly on every `create_ticket` call (multi-issue
sprint — `create_ticket`'s single-issue auto-link does not apply here).
Each ticket's `issue:` frontmatter and the corresponding issue's
`tickets:` back-reference were confirmed bidirectional after creation.

| # | Title | Depends On | Issue | Ticket |
|---|-------|------------|-------|--------|
| 001 | Retired hook events no-op instead of erroring; regression tests for both the no-op and hard-error paths | — | removed-commit-check-subcommand-breaks-stale-hook-registrations.md | [tickets/001-retired-hook-events-no-op-instead-of-erroring-regression-tests-for-both-the-no-op-and-hard-error-paths.md](tickets/001-retired-hook-events-no-op-instead-of-erroring-regression-tests-for-both-the-no-op-and-hard-error-paths.md) |
| 002 | Scope close_sprint's version-bump commit to only the files the bump step wrote | — | close-sprint-version-bump-commits-unrelated-untracked-files.md | [tickets/002-scope-close-sprint-s-version-bump-commit-to-only-the-files-the-bump-step-wrote.md](tickets/002-scope-close-sprint-s-version-bump-commit-to-only-the-files-the-bump-step-wrote.md) |
| 003 | Collapse status-inject's residual git-subprocess spawns and/or hook-process startup imports to close the sub-200ms gap | — | status-inject-residual-latency-git-spawn-and-startup.md | [tickets/003-collapse-status-inject-s-residual-git-subprocess-spawns-and-or-hook-process-startup-imports-to-close-the-sub-200ms-gap.md](tickets/003-collapse-status-inject-s-residual-git-subprocess-spawns-and-or-hook-process-startup-imports-to-close-the-sub-200ms-gap.md) |

Tickets execute serially in the order listed, sequenced by urgency
(001 is an active, field-reported break) rather than by dependency —
all three are independent, single-issue fixes in different modules
with no shared files and no real ordering constraint between them.
