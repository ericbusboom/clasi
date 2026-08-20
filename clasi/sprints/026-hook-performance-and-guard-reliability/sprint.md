---
id: '026'
title: Hook performance and guard reliability
status: planning-docs
branch: sprint/026-hook-performance-and-guard-reliability
worktree: false
use-cases: []
issues:
- hook-overhead-status-inject-dead-hooks-and-logging.md
- guard-dead-ends-no-ticket-gate-scope-and-close-sprint-recovery.md
- role-guard-tier1-design-dir-and-initiation-skill-hardcoded-path.md
- programmer-agents-stall-on-background-pytest.md
- status-exclude-done-filter-misses-closed-sprints.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 026: Hook performance and guard reliability

## Goals

Cut hook-path latency and overhead that taxes every prompt and every
Bash call, and fix three guard/gate dead ends that block agents with no
in-process route forward. Four issues, one theme: the enforcement/status
hook layer (`hook_handlers.py` plus its `status`/`state_machine`/`tools`
collaborators) is both too slow and too eager to fail closed with no
recovery path.

1. `status-inject` costs about 1s of blocking latency per user prompt and
   injects about 900 tokens of mostly-noise YAML; dead hook registrations
   (`commit-check`, `TaskCreated`, `TaskCompleted`) tax every Bash call for
   zero benefit; `hooks.log` cannot record which file was blocked or on
   what day.
2. The ticket-state gate blocks every tier (including issue/reflection
   writes needed for incident capture) whenever an execution lock is held
   with no ticket in-progress — exactly the state a thrown exception
   creates. `close_sprint`'s own recovery-instruction branches don't write
   the recovery state that would unblock the fix they ask for.
3. `role-guard` has no tier-1 allow-list entry for artifact directories
   (design/issues/reflections), contradicting its own docstring matrix, so
   a sprint-planner dispatched by `project-initiation` cannot write the
   documents it's told to write. The skill also hardcodes
   `.clasi/design/` instead of resolving `Project.design_dir`.
4. Programmer sub-agents that background the test suite end their turn
   before it completes, orphaning uncommitted work and an undone ticket.
   Every programmer also redundantly runs the full suite once per ticket.

## Problem

Four independent, previously-filed issues converge on the same
enforcement/status hook layer, each identified with confirmed root causes
and file:line references (see each issue file for full evidence):

- `hook-overhead-status-inject-dead-hooks-and-logging.md`
- `guard-dead-ends-no-ticket-gate-scope-and-close-sprint-recovery.md`
- `role-guard-tier1-design-dir-and-initiation-skill-hardcoded-path.md`
- `programmer-agents-stall-on-background-pytest.md`

**Mid-execution addition**: a fifth issue,
`status-exclude-done-filter-misses-closed-sprints.md`, was filed and
linked to this sprint (`sprint: '026'`) after ticket 003 landed and
measured against the real hooks.log/fixture data — see ticket 007 below.
It is a direct consequence of the same status-inject investigation, not
a scope drift: ticket 003's own before/after measurement is what
surfaced it.

Left unaddressed, the performance cost compounds on every prompt and every
Bash call in every session, and the guard dead ends mean an agent that
hits one of these conditions (an execution-lock sprint with no ticket
in-progress, a tier-1 write to the configured design dir, a `close_sprint`
frontmatter-fence error) has no sanctioned way forward except OOP.

## Solution

Bundle the four issues into one sprint because they share files
(`hook_handlers.py`'s `handle_role_guard` is the single most-touched
function — issues 2 and 3 both edit it, and issue 1's per-invocation
caching work touches it too) and share a verification discipline: every
guard-behavior change gets a regression test using a real captured hook
payload asserting both the allow and the deny path, and every
performance change gets a before/after `time` measurement. Tickets are
sequenced so that all `handle_role_guard` edits land in one ticket
(001) before anything that depends on its new behavior (tier-1 write
success, the scoped ticket-gate) is exercised in a later ticket's tests.

## Success Criteria

- `time clasi hook status-inject < captured-payload.json` drops from
  about 1.05-1.15s to under 200ms, with unchanged status content (beyond
  the intentionally trimmed noise) for a project with active ticketed
  sprints. **Completed by ticket 007, not ticket 003 alone**: 003
  delivered its four planned caching/trimming changes but landed at
  median about 0.78s in this repo, because of a pre-existing gap outside
  003's scope — `_build_sprints_block`'s `exclude_done` filter matches
  only `status: done`, so the six archived sprints under
  `clasi/sprints/done/` (020-025), which declare `status: closed`, leak
  past the filter and get fully re-evaluated every invocation (137
  `get_sprint()` calls, 1,816 `read_frontmatter()` calls per prompt; 7
  sprints evaluated instead of 1). Ticket 007 widens the terminal-state
  exclusion to close this criterion. See ticket 003's Measurement Notes
  (`tickets/done/003-...md`) for full detail.
- `commit-check`, `TaskCreated`, `TaskCompleted` are absent from a fresh
  `clasi init` fixture's installed hook settings.
- `hooks.log` lines carry dated timestamps and a real `file_path` on
  block events after a working session.
- A tier-2 write with an execution lock held and zero tickets
  in-progress is still blocked (`no-ticket`); the same state no longer
  blocks tier-0/1 writes, or issue/reflection writes from any tier.
- `close_sprint`'s frontmatter-fence and id-mismatch branches leave a
  recovery record whose named path a follow-up guarded `Edit` can then
  write, with reason `recovery`.
- A tier-1 sprint-planner dispatched per `project-initiation` can write
  `overview.md`/`specification.md`/`usecases.md` to the project's
  configured `design_dir`, whatever it is set to.
- A programmer sub-agent never ends its turn with a backgrounded test run
  and an unmarked ticket; the full suite runs exactly once per sprint
  (at the close gate), not once per ticket.
- Every guard-behavior regression test added this sprint asserts both
  the allow and the deny path against a real captured payload; no
  existing deny-path assertion is weakened.

## Scope

### In Scope

- `hook_handlers.py`: `handle_role_guard` (tier-1 allow-list, ticket-gate
  scope, recovery-path matching, block-message identity, per-invocation
  caching), `_log_hook_event` (file_path source, dated timestamps).
- `status/reader.py` (`ClasiStateReader` git-call memoization),
  `state_machine/loader.py` (`load_machine` caching),
  `hook_handlers.py`'s status-inject path (drop `detect_inconsistencies`
  from the hook, trim injected YAML).
- `plugin/hooks/hooks.json` (remove dead registrations, add explicit
  timeouts), `__init__.py` (lazy `__version__`), this repo's own
  `.claude/settings.json` (drift alignment).
- `tools/artifact_tools.py`'s `_close_sprint_full` (recovery-state writes
  on the frontmatter-fence and id-mismatch branches).
- `plugin/skills/project-initiation/SKILL.md` and sibling skill/agent
  docs hardcoding `.clasi/design/`.
- `plugin/agents/programmer/*` (no-background test discipline, scoped
  test runs), the execute-sprint/close-sprint single full-suite gate.
- Optional (stretch, explicitly "consider" in the source issue): a guard
  hook denying `run_in_background` Bash calls from tier-2 dispatches.

### Out of Scope

- `report-guard-friction-slowness-relax-tier-0-restrictions.md` — a
  related but separate policy issue (tier-0 restriction relaxation),
  not claimed by this sprint.
- Any other currently-pending issue in `clasi/issues/` not listed above
  (`clasi-init-reverts-...`, `claude-cli-rejects-...`,
  `db-backed-oop-flag-...`, `get-project-has-no-upward-...`,
  `sprint-planner-tier-1-may-never-be-set-...`) — untouched by this
  sprint.
- Harness-level fixes for sub-agent backgrounding (item 4 of issue 4's
  ranked proposals) — out of CLASI's control, documented as a known
  limitation only.
- Staleness-check performance — issue 1 explicitly flags this as
  already cheap (0.6-1.1ms) and out of scope for this investigation.

## Test Strategy

- **Guard-behavior changes** (tickets 001, 002, 007): regression tests
  using real captured hook payloads (not synthetic), each asserting both
  the allow path and the deny path. No existing deny-path test is
  weakened.
- **Performance changes** (tickets 001's caching, 003, 004): before/after
  `time clasi hook <name> < captured-payload.json` measurements recorded
  in the ticket's acceptance criteria, plus a call-count assertion
  (mock/debug-counter) for the specific redundant calls being eliminated
  (git subprocesses, `load_machine` parses, `get_project()`/config/sqlite
  calls) so the fix is verified structurally, not just by wall-clock
  variance.
- **Scenario tests**: end-to-end checks that exercise the fix from an
  agent's perspective — throw_ticket_exception then a dispatched
  sprint-planner editing the sprint's architecture without OOP (001,
  002); a tier-1 sprint-planner writing initiation docs to a
  custom-configured `design_dir` (005).
- **Full suite**: run once per ticket during ticket execution against
  the ticket's own scope per the project's existing convention, and once
  at sprint close (ticket 006 additionally establishes this as the
  sprint-execution norm going forward, per issue 4).

## Architecture

**Substantial** — 5 modules touched across this sprint's four issues:
the `clasi-core` top-level module group (`hook_handlers.py`,
`__init__.py`, described in `src/clasi/DESIGN.md`), `clasi.status`
(`reader.py`, `inconsistency.py`'s removal from the hot path),
`clasi.state_machine` (`loader.py`), `clasi.tools`
(`artifact_tools.py`'s `_close_sprint_full`), and `clasi.plugin`
(`hooks/hooks.json`, `skills/project-initiation/SKILL.md` and siblings,
`agents/programmer/*`). That is 3+ modules by the sizing rule's own
threshold, so this sprint is substantial by module count even though no
single change within it is individually large. This project has opted
into the persistent per-subsystem design-doc set
(`design_docs: enabled`), so the full write-up below is additionally
mirrored into a `clasi/sprints/026-hook-performance-and-guard-reliability/design/`
overlay for the five affected canonical `DESIGN.md` docs (seeded via
`seed_sprint_design_overlay`, edited, diffed, and validated — see
Impact on Existing Components below for the manifest).

### 1. Understand the Problem

See Problem above and each issue file's own Cause section (all four
issues carry confirmed root causes with file:line references, not
speculation). The four issues were filed independently but converge on
one function (`handle_role_guard`) and one performance pattern (no
caching across the several `get_project()`/config/git/YAML calls a
single hook invocation makes).

### 2. Identify Responsibilities

1. **Role-guard directory-scope and gate correctness**
   (`handle_role_guard`) — deciding, per tier and path, whether a write
   is allowed; currently wrong in three independent ways (missing
   tier-1 artifact-dir allow-list, ticket-gate too broad, recovery
   matching exact-path-only) plus a display-name bug in its block
   message. Changes because each of these is a confirmed defect against
   the function's own documented intent, not a new feature.
2. **Role-guard per-invocation cost** (`handle_role_guard`,
   `get_project()`, `Project._load_config`, sqlite connection setup) —
   distinct from (1): even a *correct* role-guard call today pays for
   5 `get_project()` calls, 3 config parses, and 4 sqlite connections it
   doesn't need. Changes independently of (1) — a caching concern, not a
   correctness concern — but lands in the same ticket as (1) because
   both edit the same function body and a caching refactor around
   already-changing gate logic is safer done once.
3. **status-inject latency** (`ClasiStateReader.git_branch` and its 27
   siblings, `state_machine.loader.load_machine`,
   `status.inconsistency.detect_inconsistencies`, the injected YAML
   shape) — assembling the per-prompt status block currently redoes the
   same git/YAML work dozens of times and runs a diagnostic pass
   (`detect_inconsistencies`) that a hot hook path doesn't need. Changes
   independently of (1)/(2): a different code path (status-inject, not
   role-guard) with a different fix shape (memoization, not gate logic).
4. **Dead hook registrations and log usefulness**
   (`plugin/hooks/hooks.json`, `_log_hook_event`, `__init__.py`) —
   three registrations that have never fired taxing every Bash call;
   a log that can't record what was blocked. Changes independently of
   (1)-(3): pure removal/observability work, no gate or caching logic.
5. **close_sprint recovery completeness** (`_close_sprint_full`'s
   frontmatter-fence and id-mismatch branches) — two precondition
   branches hand out recovery instructions without recording the
   recovery state that would let the guard honor them. Changes
   independently of (1)-(4): the write-side of the same recovery
   mechanism (1) reads, but a distinct module (`artifact_tools.py`, not
   `hook_handlers.py`).
6. **project-initiation path correctness** (`SKILL.md` and sibling
   docs) — instructional content hardcoding `.clasi/design/` instead of
   resolving the configured `design_dir`. Changes independently of
   (1)-(5): documentation content, not code; depends on (1)'s tier-1
   allow-list fix to be *effective*, but is itself a separate edit to a
   separate set of files.
7. **Programmer test-run discipline** (`agents/programmer/*`,
   execute-sprint/close-sprint full-suite ownership) — agent-definition
   prompt content, not hook code. Changes independently of everything
   above: a different failure mode (harness turn-ending on background
   task) with a different fix shape (prompt rule plus process
   re-ownership, not a code change).
8. **Optional background-task guard** (a new `hook_handlers.py`
   handler, a new `hooks.json` registration) — the stretch enforcement
   layer for (7), explicitly framed as "consider" in its source issue.
   Changes independently of (7) itself (belt-and-suspenders, not a
   prerequisite) but shares (4)'s file (`hooks.json`) closely enough to
   sequence after it.

### 3. Define Subsystems and Modules

- **`clasi-core` / `hook_handlers.py`** — purpose: decide, per hook
  event, whether to allow or block a tool call, and log the decision.
  Boundary: reads `Project`, `StateDB`, and the payload; never mutates
  artifact content itself. Serves SUC-003, SUC-004, SUC-005, SUC-006,
  SUC-007, SUC-008, SUC-009 (optional guard).
- **`clasi.status`** (`reader.py`, `inconsistency.py`) — purpose: turn
  declarative state-machine evaluation into a concrete per-prompt status
  report. Boundary unchanged (per its own `DESIGN.md`); this sprint adds
  a caching layer inside `ClasiStateReader` and removes
  `detect_inconsistencies` from one specific caller (the hook path),
  not from the subsystem's public API. Serves SUC-001.
- **`clasi.state_machine`** (`loader.py`) — purpose: parse and construct
  `Machine` objects from packaged YAML. Boundary unchanged; this sprint
  adds process-lifetime memoization so the same three machine names
  aren't re-parsed on every call within one hook invocation. Serves
  SUC-001.
- **`clasi.tools`** (`artifact_tools.py`) — purpose: the MCP-callable
  artifact-lifecycle surface. Boundary unchanged; this sprint extends
  `_close_sprint_full`'s existing recovery-state pattern (already used
  by its ticket-not-done branch) to two branches that currently omit it.
  Serves SUC-005.
- **`clasi.plugin`** (`hooks/hooks.json`, `skills/project-initiation/`,
  `agents/programmer/`) — purpose: the packaged content root installers
  copy into a target repo. Boundary unchanged (content, not code); this
  sprint edits hook wiring and instructional prose. Serves SUC-002,
  SUC-003, SUC-007, SUC-009, SUC-010.

No new module or subsystem is introduced. Every change corrects,
caches, or trims behavior inside a module that already owns that
responsibility.

### 4. Diagrams

Omitted by reasoned exception, matching sprint 020's precedent: this
sprint's five touched modules already depend on each other in exactly
the shape a component diagram would show (`hook_handlers.py` calls
`clasi.status`/`clasi.state_machine` for status-inject, `Project`/
`StateDB` for role-guard; `tools/artifact_tools.py` calls `StateDB`
directly) — none of that is new, none of it is being redirected, and no
new cross-module dependency or dependency-direction change is
introduced anywhere in this sprint. Each fix operates entirely within
one existing module's own responsibility (caching inside `reader.py`,
gate logic inside `handle_role_guard`, a second recovery-state call
site inside `artifact_tools.py`). A diagram would only repeat the
existing, unchanged module map already documented in
`src/clasi/DESIGN.md`. No ERD — no data-model change (the `active_agents`
and recovery-state SQLite tables keep their existing shape; this sprint
only writes to columns/rows that already exist, from two additional
call sites). No dependency graph — no dependency added, removed, or
redirected.

### 5. What Changed / Why / Impact / Migration Concerns

**What Changed**:
- `handle_role_guard`: tier-1 gains the artifact-dir allow list
  (design/issues/reflections/clasi-state/log); the ticket-state gate is
  scoped to tier 2 only, with `issues_dir`/`reflections_dir` exempt for
  all tiers; recovery-path matching honors directory-prefix entries, not
  just exact paths; the block message resolves the display name from
  the state DB (`get_active_agent`) when the tier itself came from the
  DB; a single `Project` instance and single sqlite connection are
  reused across the checks in one invocation instead of being
  reconstructed per check.
- `ClasiStateReader`: per-invocation memoization of its git-subprocess
  methods (28 calls collapse to about 3 for a typical status-inject
  call). `load_machine`: `lru_cache`d (20 re-parses collapse to 3, one
  per machine name, for the life of the process). The status-inject hook
  path stops calling `detect_inconsistencies` (still available via
  `clasi status` and the project-status skill) and trims
  `available_transitions`/`blocked_by` detail for empty pre-flight
  sprints.
- `plugin/hooks/hooks.json` loses the `commit-check` (`PostToolUse`/
  `Bash`), `TaskCreated`, and `TaskCompleted` registrations; all
  remaining registrations gain explicit `timeout` values. `__init__.py`
  resolves `__version__` lazily via module `__getattr__` instead of an
  eager `importlib.metadata.version` call at import time. `_log_hook_event`
  reads `file_path` from `tool_input` (not the payload top level) and
  timestamps gain a date component. This repo's own `.claude/settings.json`
  is realigned with the plugin's `hooks.json` (dropping the `uv run`
  prefix drift).
- `_close_sprint_full`'s frontmatter-fence and sprint-id-mismatch
  branches call `db.write_recovery_state(...)` with the offending
  `sprint.md` path, matching the pattern already used by the
  ticket-not-done branch.
- `project-initiation/SKILL.md` and sibling docs
  (`software-engineering.md`, `sprint-planner/plan-sprint.md`,
  `sprint-planner/agent.md`, `team-lead/project-status.md`,
  `sprint-roadmap/SKILL.md`, `project-status/SKILL.md`,
  `architecture-authoring/SKILL.md`, `migrate_command.py`) stop
  hardcoding `.clasi/design/` and instead resolve the configured
  `design_dir`.
- `agents/programmer/*` gains an explicit no-background-test-run rule
  and scopes test runs to the ticket; execute-sprint/close-sprint
  documents owning the single full-suite run before close. Optionally,
  a new hook handler denies `run_in_background: true` Bash calls from
  tier-2 dispatches.

**Why**: see each issue file's Cause section; every change above traces
to a specific confirmed defect or measured cost, not a speculative
improvement.

**Impact on Existing Components**: None of these changes alter any
public MCP tool signature, CLI command shape, or artifact frontmatter
schema. The status YAML shape is unchanged except for the intentional
trim (verified by a regression test comparing the full-detail case for
a project with active ticketed sprints). The recovery-state DB table's
schema is unchanged — two additional call sites write to it, using the
same shape existing callers already use. `hooks.json`'s removed
registrations correspond to handler functions that have produced zero
log lines across 2,447 recorded events — dead on both ends. Design-doc
impact: `src/clasi/DESIGN.md`, `src/clasi/status/DESIGN.md`,
`src/clasi/state_machine/DESIGN.md`, `src/clasi/tools/DESIGN.md`, and
`src/clasi/plugin/DESIGN.md` are updated via this sprint's `design/`
overlay to describe the caching/gate/logging behavior changes above;
none of the five docs' Purpose, Boundary, or Interfaces sections change
— only their Constraints/Design prose gains a note about the new
caching or gate-scope behavior. See the overlay's `.diff.md` files for
the exact per-doc changes.

**Migration Concerns**: None. No data migration (no schema change); no
breaking interface change (every MCP tool and CLI command keeps its
existing signature); no deployment-sequencing concern (hook and skill
content is reinstalled via the normal `clasi init`/migrate path, not a
live-upgrade path with in-flight state to preserve). Existing sprints
with an execution lock held and a ticket already in-progress are
unaffected by the ticket-gate scoping change (tier-2 behavior is
unchanged when a ticket *is* in-progress; only the previously-blocked
tier-0/1/issues/reflections cases change).

### 6. Design Rationale

**Decision**: consolidate all `handle_role_guard` edits (tier-1
allow-list, ticket-gate scope, recovery-path matching, block-message
identity, per-invocation caching) into a single ticket (001) rather than
one ticket per issue.

**Context**: issues 2 and 3 both specify changes to `handle_role_guard`,
and issue 1's "one cached Project and one sqlite connection per
role-guard invocation" fix also lives inside that same function. Three
of this sprint's four issues therefore converge on one function body.

**Alternatives considered**: one ticket per issue (three separate
tickets each editing `handle_role_guard`) — rejected because three
tickets editing the same ~350-line function serially would each need to
re-read the others' in-flight edits to avoid clobbering them, and the
dependency chain (005 needs 001's allow-list fix to be end-to-end
testable) would still force near-total serialization anyway, so
splitting gains no real parallelism while adding merge risk.

**Why this choice**: one ticket per shared function eliminates the
serial-edit risk entirely and lets a single set of regression tests
(allow and deny paths for every changed condition) be written and
verified together against the function's final state, rather than
against three intermediate states.

**Consequences**: ticket 001 is larger than the sprint's other tickets
(five distinct fixes plus a caching refactor, all in one function) —
acceptable because it is still one function, one file, one focused
session's worth of related work, and every other ticket in this sprint
that touches `handle_role_guard`-adjacent behavior (005's end-to-end
scenario, 007's optional guard) depends on 001 being complete first
rather than racing it.

### 7. Open Questions

- **Ticket 007 (optional background-task guard)**: issue 4 frames CLASI-
  level enforcement as "consider," not a firm requirement — the
  stakeholder should confirm whether this stretch ticket stays in scope
  for this sprint or is deferred to a future one. Flagged for
  stakeholder attention in this sprint's planning handoff.
- **`.claude/agents/programmer/*` vs. `src/clasi/plugin/agents/programmer/*`**:
  this repo's own installed agent copies are normally regenerated from
  the packaged `plugin/` source via `clasi init`/migrate, not hand-edited
  in parallel. Ticket 006 edits the canonical `plugin/` source; whether
  this repo's own installed `.claude/agents/programmer/*` needs a
  companion re-install/migrate step to pick up the change (versus
  drifting until the next migrate) is left to that ticket's
  implementation to confirm against the existing installer convention.
- **`migrate_command.py`'s `.clasi/design/` references**: some hits from
  `grep -rl '\.clasi/design'` in that file may be legitimate
  migration-source-path literals (the old location migrate reads *from*),
  not instructional defaults to fix. Ticket 005 must review each hit
  individually rather than blanket-replacing every occurrence.

## Use Cases

### SUC-001: Fast per-prompt status injection
Parent: UC-013

- **Actor**: Any agent (team-lead, sprint-planner, programmer) submitting a prompt.
- **Preconditions**: A CLASI project with at least one sprint on disk.
- **Main Flow**:
  1. The agent submits a prompt; the `UserPromptSubmit` hook fires `clasi hook status-inject`.
  2. `ClasiStateReader` answers each state-machine predicate using at most one git subprocess call per distinct git query, not one per predicate.
  3. `load_machine` returns a cached `Machine` for a name already loaded this process.
  4. The hook does not run `detect_inconsistencies`; it returns the status YAML with per-prompt-irrelevant transition detail trimmed for empty pre-flight sprints.
- **Postconditions**: The status block is injected in under 200ms; its content is unchanged (beyond the intentional trim) for a project with active ticketed sprints.
- **Acceptance Criteria**:
  - [ ] `time clasi hook status-inject < captured-payload.json` is under 200ms after the fix (was about 990ms-1.1s before).
  - [ ] Git-subprocess call count per invocation drops from about 28 to about 3 (asserted via mock/debug counter).
  - [ ] `load_machine` parse count per invocation drops from about 20 to 3 (one per machine name).
  - [ ] `clasi status` CLI and the project-status skill still surface inconsistency detection unchanged.

### SUC-002: Diagnosable hook log
Parent: UC-013

- **Actor**: A developer investigating guard friction after a session.
- **Preconditions**: One or more hook invocations have occurred, including at least one blocked write.
- **Main Flow**:
  1. `_log_hook_event` reads `file_path` from `payload["tool_input"]`, matching the actual Claude Code payload shape.
  2. It writes a timestamp that includes the date, not just `%H:%M:%SZ`.
- **Postconditions**: `hooks.log` lines for block events name the file that was blocked, and lines from different days are distinguishable.
- **Acceptance Criteria**:
  - [ ] A synthetic and a real blocked-write payload both produce a `hooks.log` line carrying a non-empty `file_path`.
  - [ ] Timestamps include a date component.

### SUC-003: No dead hook overhead on every Bash call
Parent: UC-002

- **Actor**: Any agent invoking the Bash tool.
- **Preconditions**: A fresh `clasi init` install or this repo's own `.claude/settings.json`.
- **Main Flow**:
  1. The agent calls Bash.
  2. No `commit-check` hook fires (it read `os.environ["TOOL_INPUT"]`, which Claude Code never sets, and has produced 0 of 2,447 logged events).
- **Postconditions**: Bash calls no longer pay the removed hook's process-startup floor (about 90ms).
- **Acceptance Criteria**:
  - [ ] `commit-check`, `TaskCreated`, `TaskCompleted` are absent from a fresh `clasi init` fixture's installed hook settings.
  - [ ] `time clasi hook role-guard < captured-payload.json` shows the startup-floor savings (no eager metadata scan; single config parse — observable via a debug counter or strace/dtruss open-call count).

### SUC-004: Ticket-gate scoped to tier 2, incident capture always allowed
Parent: UC-002

- **Actor**: A team-lead, dispatched sprint-planner, or programmer during an active sprint execution lock with zero tickets in-progress (e.g. immediately after `throw_ticket_exception`).
- **Preconditions**: An execution lock is held for a sprint with no ticket `in-progress`.
- **Main Flow**:
  1. A tier-2 agent attempts a source/test write — blocked (`no-ticket`), unchanged from today.
  2. A tier-0 or tier-1 agent attempts a write to an allow-listed path — no longer blocked by the ticket-gate.
  3. Any tier attempts a write under `issues_dir` or `reflections_dir` — never blocked by the ticket-gate.
- **Postconditions**: Only tier-2 source/test writes are gated by ticket state; incident-capture and recovery writes are never dead-ended by it.
- **Acceptance Criteria**:
  - [ ] Real captured payload, tier-2 source write, lock held, zero in-progress tickets → blocked (`no-ticket`).
  - [ ] Real captured payload, tier-0/1 write to an allow-listed path, same state → allowed.
  - [ ] Real captured payload, any tier, write under `issues_dir`/`reflections_dir`, same state → allowed.
  - [ ] Scenario test: `throw_ticket_exception` → a dispatched sprint-planner can edit the sprint's architecture without OOP.

### SUC-005: close_sprint precondition failures leave a usable recovery path
Parent: UC-005

- **Actor**: A team-lead calling `close_sprint` against a sprint whose `sprint.md` has a broken frontmatter fence or a missing/incorrect `id:` field.
- **Preconditions**: `close_sprint` is called and hits the frontmatter-fence-error or id-mismatch precondition branch.
- **Main Flow**:
  1. `close_sprint` returns its existing recovery instruction (edit `sprint.md` and retry).
  2. It also calls `db.write_recovery_state(...)` naming the offending `sprint.md` path.
  3. The team-lead's follow-up guarded `Edit` of that exact file passes with reason `recovery`.
- **Postconditions**: The recovery instruction `close_sprint` gives is actually actionable without an OOP bypass.
- **Acceptance Criteria**:
  - [ ] `close_sprint` against a sprint.md with a broken frontmatter fence → response includes populated `allowed_paths`.
  - [ ] A follow-up guarded `Edit` of that file passes with reason `recovery`.
  - [ ] Same for the sprint-id-mismatch branch.

### SUC-006: Recovery state matches directory entries, not just exact paths
Parent: UC-005

- **Actor**: Any guard-checked write during sprint recovery.
- **Preconditions**: A recovery record's `allowed_paths` contains a directory entry (e.g. `str(project.design_dir)`), as at least one existing writer already stores.
- **Main Flow**:
  1. An agent writes a file under that directory.
  2. Role-guard's recovery-state check normalizes both the stored entry and the candidate path and matches on directory-prefix, not just exact equality.
- **Postconditions**: Directory entries in `allowed_paths` are no longer silently inert.
- **Acceptance Criteria**:
  - [ ] Recovery record containing a directory entry → a file write under that directory passes with reason `recovery`.
  - [ ] Exact-path entries continue to match exactly (no regression).

### SUC-007: Tier-1 can write to the project's configured design directory
Parent: UC-001

- **Actor**: A sprint-planner (tier 1) dispatched by `project-initiation`.
- **Preconditions**: A project with `paths.design: docs/design` (or any configured `design_dir`) and no `protected_paths:`.
- **Main Flow**:
  1. The sprint-planner writes `overview.md`/`specification.md`/`usecases.md`.
  2. `handle_role_guard` checks the `_allow_prefixes` list (design/issues/reflections/clasi-state/log) for tier 1, matching the function's own documented matrix.
  3. `project-initiation/SKILL.md` instructs writing to the resolved `design_dir`, not a hardcoded `.clasi/design/` literal.
- **Postconditions**: The write succeeds and lands where `overview_exists()`/`is_overview_present` actually looks, so the `initialize` transition is not permanently blocked.
- **Acceptance Criteria**:
  - [ ] Real captured payload, tier 1, write to configured `design_dir` → allowed (`artifact-dir`).
  - [ ] Real captured payload, tier 1, write to a source path → still blocked.
  - [ ] End-to-end: project with `paths.design: docs/design`, no `protected_paths` — a dispatched sprint-planner's initiation-document writes succeed and the project advances past `uninitialized`.

### SUC-008: Role-guard block message names the actual registered role
Parent: UC-002

- **Actor**: Any agent whose write is blocked by role-guard.
- **Preconditions**: The agent's tier was resolved from the state DB (not the `CLASI_AGENT_TIER` env var).
- **Main Flow**:
  1. The write is blocked.
  2. The block message's agent name is looked up via `get_active_agent` for `caller_id`, the same source the tier came from — not the `CLASI_AGENT_NAME` env default.
- **Postconditions**: The block message never contradicts itself (e.g. "team-lead (tier 1)").
- **Acceptance Criteria**:
  - [ ] Real captured payload, tier resolved from DB → block message names the DB-registered agent, not the env default.

### SUC-009: Programmer sub-agents never stall on a backgrounded test run
Parent: UC-010

- **Actor**: A dispatched programmer sub-agent finishing a ticket's code changes.
- **Preconditions**: The ticket's code changes are complete and ready for the test gate.
- **Main Flow**:
  1. The programmer runs its ticket-scoped tests in the foreground (never `run_in_background: true`).
  2. It stays alive to see the result, commits, and marks the ticket done in the same turn.
- **Postconditions**: No ticket is left uncommitted with a backgrounded test run the agent never returns to.
- **Acceptance Criteria**:
  - [ ] Programmer agent definition states the no-background rule explicitly and states a ticket is not done until committed.
  - [ ] Programmer agent definition scopes test runs to the ticket, not the full suite.
  - [ ] **Deferred** (was ticket 007, stretch): a guard hook denying `run_in_background: true` Bash calls from tier-2 dispatches, verified allow/deny with real captured payloads. Deferred out of this sprint's scope by stakeholder decision 2026-08-19; this sprint satisfies SUC-009 via the first two criteria (prompt-level agent-definition fix) only.

### SUC-010: The full test suite runs once per sprint, not once per ticket
Parent: UC-010

- **Actor**: The team-lead / execute-sprint process.
- **Preconditions**: A sprint with N tickets is being executed.
- **Main Flow**:
  1. Each programmer runs only its ticket-scoped tests.
  2. execute-sprint / the close-sprint gate runs the full suite exactly once, before close.
- **Postconditions**: The full suite's wall-clock cost is paid once per sprint, not N times.
- **Acceptance Criteria**:
  - [ ] execute-sprint (or close-sprint) skill/gate documentation states it owns the single full-suite run.
  - [ ] Programmer agent definition no longer instructs running the full suite per ticket.

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [x] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [x] Stakeholder has approved the sprint plan — approved 2026-08-19;
      `stakeholder_approval` gate recorded
      (`record_gate_result(sprint_id="026", gate="stakeholder_approval",
      result="passed")`). Ticket 007 (stretch) was deferred out of this
      sprint's scope as part of the same approval — see Tickets below.

## Tickets

Materialized as tickets 001-007 in `tickets/` (001-003 done and
committed; see below for mid-execution ticket 007). The **original**
stretch ticket 007 (a CLASI-level guard hook denying `run_in_background`
from tier-2 dispatches) was **deferred by stakeholder decision** during
approval and was never created — issue 4
(`programmer-agents-stall-on-background-pytest.md`) is fully addressed
within this sprint's scope by ticket 006 alone (the source issue's
required proposals #1/#2); that deferred item remains available to pick
up in a future sprint if the prompt-level fix in ticket 006 proves
insufficient in practice. The id `007` was free and has since been
reused below for unrelated, mid-execution work — **it is not the
deferred stretch item.**

| # | Title | Depends On | Issue(s) |
|---|-------|------------|----------|
| 001 | role-guard consolidated hardening: tier-1 allow list, ticket-gate scope, recovery-path matching, per-invocation caching, block-message identity | — | hook-overhead-status-inject-dead-hooks-and-logging.md, guard-dead-ends-no-ticket-gate-scope-and-close-sprint-recovery.md, role-guard-tier1-design-dir-and-initiation-skill-hardcoded-path.md |
| 002 | close_sprint: recovery-state writes on frontmatter-fence and id-mismatch branches | — | guard-dead-ends-no-ticket-gate-scope-and-close-sprint-recovery.md |
| 003 | status-inject hook performance: git-call memoization, load_machine caching, drop detect_inconsistencies, trim payload | — | hook-overhead-status-inject-dead-hooks-and-logging.md |
| 004 | Remove dead hook registrations, lazy __version__, fix hooks.log file_path/timestamps, align settings.json | — | hook-overhead-status-inject-dead-hooks-and-logging.md |
| 005 | project-initiation skill and sibling docs: resolve configured design_dir instead of hardcoded .clasi/design/ | 001 | role-guard-tier1-design-dir-and-initiation-skill-hardcoded-path.md |
| 006 | Programmer agent definition: no-background test discipline, scoped tests, single full-suite gate ownership | — | programmer-agents-stall-on-background-pytest.md |
| 007 | status sweep excludes terminal sprints: widen exclude_done to closed / archived | 003 | status-exclude-done-filter-misses-closed-sprints.md |

**Note on ticket 007**: this id was originally reserved for a stretch
guard-hook ticket that the stakeholder deferred before any ticket file
existed (see paragraph above), leaving `007` free. It was reused
mid-execution for unrelated work: ticket 003 measured status-inject at
median about 0.78s in this repo, above the sprint's `<200ms` success
criterion, tracing to a pre-existing gap in `_build_sprints_block`'s
`exclude_done` filter (matches `status: done` only, missing the
`status: closed` archived sprints under `clasi/sprints/done/`). The
stakeholder filed and linked the resulting issue
(`status-exclude-done-filter-misses-closed-sprints.md`) and requested
this ticket. It depends on 003 (already done) and closes the sprint's
`<200ms` success criterion — see Success Criteria above.

Tickets execute serially in the order listed. 005 depends on 001's
tier-1 allow-list fix being in place for its end-to-end scenario test to
pass; 007 depends on 004 to avoid both tickets editing `hooks.json`
concurrently. 002, 003, 004, and 006 have no dependencies and could run
in parallel if this sprint later opts into worktree execution.
