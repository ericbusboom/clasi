---
id: '024'
title: Guard/gate correctness and close-gate reliability
status: planning-docs
branch: sprint/024-guard-gate-correctness-and-close-gate-reliability
worktree: false
use-cases: []
issues:
- team-lead-agent-doc-contradicts-mcp-guard-on-create-sprint.md
- sprint-planner-tier-1-may-never-be-set-verify-clasi-agent-tier-wiring.md
- role-guard-blocks-plan-mode-plans-dir.md
- db-backed-oop-flag-file-as-unconditional-override.md
- close-sprint-test-timeout-hardcoded-300s-too-short.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 024: Guard/gate correctness and close-gate reliability

## Goals

Close out a batch of five pending guard/gate correctness issues, plus one
unrelated small close-gate reliability fix bundled in because it is small
and self-contained. Four of the five issues are in the same family: a
documented workflow or enforcement mechanism disagreeing with what the
guard code actually does (role-guard, mcp-guard, tier resolution, the OOP
override). The fifth (`close_sprint`'s test timeout) is unrelated to
guards but is small and rides along.

This is a roadmap-mode placeholder only. Architecture, use cases, and
tickets are written when this sprint is detail-promoted.

## Problem

Several guard/gate mechanisms have drifted from the workflows and docs
that describe them, or have never been verified end-to-end:

- The team-lead agent doc instructs a direct `create_sprint` call that
  the mcp-guard hook now blocks at tier 0 — every team-lead session that
  follows the documented flow hits this wall.
- It is unverified whether `CLASI_AGENT_TIER=1` is ever actually set for
  a real sprint-planner dispatch; the sprint-planner has never once
  resolved to reason `tier-1` in the hooks log, unlike programmers which
  reliably reach `tier-2`.
- The role-guard fails closed on tier-0 writes outside the project root,
  which blocks Claude Code's own plan-mode plan file
  (`~/.claude/plans/<name>.md`) — the exact artifact clasi's own
  plan-to-issue pipeline consumes.
- The OOP bypass is a zero-byte marker file checked via a bare relative
  path, so it can silently fail to be found depending on the hook
  process's cwd, and it has no audit trail (who set it, when, why).
- `close_sprint` hardcodes a 300s test-suite timeout that is shorter than
  this repo's own suite runtime (about 460-525s), so a normal healthy
  close of any CLASI sprint times out at the tests step.

## Solution

(High-level description of the approach — to be filled in when this
sprint is detail-promoted with full architecture.)

## Success Criteria

(How will we know the sprint succeeded — to be filled in at detail
promotion.)

## Scope

### In Scope

- `team-lead-agent-doc-contradicts-mcp-guard-on-create-sprint.md` —
  reconcile the team-lead agent doc with the mcp-guard's tier-0 block on
  `create_sprint` (pick and align one of the two proposed options).
- `sprint-planner-tier-1-may-never-be-set-verify-clasi-agent-tier-wiring.md`
  — instrument and verify whether `CLASI_AGENT_TIER=1` is ever set for a
  real sprint-planner dispatch; explain the programmer (tier-2)/planner
  (never tier-1) asymmetry; determine whether the `active_agents` DB
  fallback is load-bearing or dead; add the end-to-end dispatch test the
  issue specifies.
- `role-guard-blocks-plan-mode-plans-dir.md` — allow-list
  `~/.claude/plans/` (absolute-path comparison) in `handle_role_guard` for
  tier 0, without opening a general outside-root escape.
- `db-backed-oop-flag-file-as-unconditional-override.md` — the DB-backed
  OOP redesign (new `oop_state` table, `StateDB` methods, `_oop_active()`
  rewrite with file-override-first ordering, loud status-block reporting,
  `clasi oop on|off|status` CLI, docs rewording). **Note**: the narrower
  cwd-resolution bug this issue also describes was already fixed
  out-of-process on 2026-07-17 (see the issue's own text) — what remains
  in scope here is the DB-backed redesign (auditability, TTL,
  reconciliation reporting), not the cwd fix itself.
- `close-sprint-test-timeout-hardcoded-300s-too-short.md` — make
  `close_sprint`'s test-suite timeout configurable (parameter and/or
  config key), default raised to fit a real suite, timeout value
  surfaced in the error message.

### Suggested execution order (dependency / risk informed)

1. **Team-lead/mcp-guard doc contradiction** (issue 1) — smallest, and
   unblocks clean team-lead behavior for every other dispatch in this
   sprint and beyond.
2. **Tier wiring investigation** (issue 2) — an investigation-then-fix;
   independent of the other guard issues but should land before or
   alongside them since its findings (whether `CLASI_AGENT_TIER=1` is
   ever set) may bear on how confidently later guard fixes can be trusted
   to route correctly.
3. **role-guard plans-dir block** (issue 3) — a small, precise fix in the
   same guard-inconsistency family as issue 2.
4. **DB-backed OOP redesign** (issue 4) — the largest single piece of
   work (schema, StateDB methods, rewrite, CLI, docs); the cwd bug it
   also names is already fixed out-of-process, so this ticket work is
   scoped to the redesign only.
5. **close_sprint timeout** (issue 5) — unrelated to guards, small and
   self-contained; ordered last since nothing depends on it and it
   depends on nothing else.

### Out of Scope

- Per-session OOP scoping (blocked on the session-identity plumbing that
  issue 2 investigates; deferred per issue 4's own "out of scope"
  section).
- Fixing `get_project()`'s no-upward-search cwd assumption (named as a
  separate issue by issue 4).
- An MCP toggle tool for OOP (CLI suffices per issue 4).
- Removing legacy `.clasi-oop` read support (tolerate-on-read stays).
- The already-fixed cwd-resolution bug from issue 4 (fixed
  out-of-process 2026-07-17, prior to this sprint).

## Test Strategy

Each issue's own Verification section specifies handler-level tests with
real captured hook payloads asserting both allow and deny paths — a
recurring theme across issues 2-4, carried into ticket-level test plans
rather than re-derived:

- Guard tests use real captured payload shapes (per the project's
  gate-testing discipline established in sprints 019-020) and assert the
  **deny** path explicitly, not just the allow path — enforcement gates
  that fail open silently are the recurring defect class this sprint
  closes out.
- Issue 2's end-to-end dispatch test is the one whose absence let the
  tier-1 question go unverified: a real dispatched sprint-planner, not a
  fixture insert or hand-set env var.
- Issue 4's DB-backed OOP work needs handler-level tests on both
  `role-guard` and `mcp-guard` (helper-level tests alone missed unwired
  call sites before, per the 019-002 lesson cited in the issue), plus a
  broken-DB test (corrupt/locked DB — file override must still work) and
  the cwd-independence revert-check.
- Full suite must stay green (`uv run pytest --no-cov -q`, baseline
  2580+ per issue 4's own verification section).

## Architecture

**Substantial** — bundles five issues touching guard/gate logic across
`hook_handlers.py`, `state_db_class.py`/`state_db.py`, `cli.py`, and
`artifact_tools.py`. Three of the five (issues 1, 3, 5) are individually
trivial one-module tweaks, and issue 2 is a bounded investigation
scoped to one module's tier-resolution path. But issue 4 alone —
a new `oop_state` DB table (data-model change), new `StateDB` methods,
an `_oop_active()` rewrite, status-block reporting, a new `cli.py`
command group, and doc rewording across `_rules.py`, guard error
strings, and a plugin skill — touches 4+ modules and introduces a new
cross-module dependency (`hook_handlers.py`'s OOP check reading through
`state_db`, mirroring but distinct from the existing lock/recovery
pattern). Per the sizing guidance, a sprint's tier follows its heaviest
constituent, so the whole sprint is sized substantial rather than
splitting the sizing per-issue. Diagrams are included only where they
clarify something a prose module list would not (see Step 4 below);
issues 1, 2, 3, and 5 are each independently no-diagram cases in the
same spirit as sprint 020 — many small, independent fixes with no new
composition between them.

### Step 1: Understand the Problem

Five pending issues, four in one family (a guard, gate, or tier
mechanism has drifted from the documented workflow or contract that
describes it) plus one unrelated small reliability fix riding along
because it's small and self-contained:

1. **Team-lead/mcp-guard doc contradiction** — the team-lead agent doc
   instructs a direct `create_sprint` call the mcp-guard hook blocks at
   tier 0. Fix: align the doc to the guard (Option A from the issue) —
   the team-lead dispatches sprint-planner to create the sprint, then
   runs `link_sprint_issues` after recovering the sprint id from the
   planner's report.
2. **Tier wiring verification** — unverified whether `CLASI_AGENT_TIER=1`
   is ever set for a real sprint-planner dispatch, unlike programmers
   which reliably reach tier 2. Investigation-first: instrument real
   dispatches, explain the asymmetry, determine whether the
   `active_agents` DB fallback is load-bearing, then add the end-to-end
   dispatch test — the fix depends on what the instrumentation shows.
3. **role-guard plans-dir block** — `handle_role_guard` fails closed on
   all outside-project-root paths, which blocks Claude Code's own
   plan-mode file at `~/.claude/plans/`, the same file clasi's
   `plan_to_issue` pipeline consumes. Fix: allow-list that one absolute
   path for tier 0 without opening a general outside-root escape.
4. **DB-backed OOP redesign** — the OOP bypass is a zero-byte marker
   file with no audit trail. The narrower cwd-resolution defect this
   issue also named is **already fixed** (`_find_project_root` in
   `hook_handlers.py`, confirmed present in current source, landed
   out-of-process 2026-07-17) — not re-touched here. What remains: a DB
   channel for auditability (reason, timestamp, TTL) with the file kept
   as the unconditional fire-axe override, checked first, so the escape
   never depends on the machinery it escapes.
5. **close_sprint timeout** — a hardcoded 300s test-suite timeout is
   shorter than this repo's own suite (about 460-525s). Fix: make it
   configurable with a higher default, unrelated to the guard family.

### Step 2: Identify Responsibilities

- **Tier-0 workflow documentation** (issue 1): keeping the team-lead
  agent doc's instructions executable against the guards as configured.
  Changes only when the guard's tier-0 allow/deny surface changes.
- **Tier resolution correctness** (issue 2): whether
  `CLASI_AGENT_TIER` reaches the value the guard branches on for each
  agent type, and whether the DB fallback (`active_agents`) is a live
  or dead path. Changes when dispatch wiring or the tier-resolution
  branch in `hook_handlers.py` changes.
- **role-guard path allow-listing** (issue 3): which absolute/relative
  paths a given tier may write to. Changes when a new legitimate
  outside-root write target is identified.
- **OOP bypass state and reporting** (issue 4): where the bypass state
  lives (file vs DB), how it's read/written/expired, and how its
  activity is surfaced. This is the one responsibility group touching
  the data model — a new singleton table — and it cuts across
  `state_db_class.py` (storage), `hook_handlers.py` (the read path
  every guard consults), `cli.py` (the write path an operator uses),
  and docs (the contract operators read).
- **close-gate test execution** (issue 5): how long `close_sprint` waits
  for the test command before declaring a timeout. Independent of every
  other responsibility here — no shared code path with the guard family.

These five groups are independent of each other (no responsibility
here changes for the same reason another one does), which is why they
ticket separately rather than folding into fewer, broader tickets.

### Step 3: Define Subsystems and Modules

- **`hook_handlers.py`** (existing, loose top-level module per
  `docs/design/design.md`'s subsystem map) — purpose: dispatch Claude
  Code hook events to allow/deny/report decisions. Boundary: reads
  stdin JSON payloads and project/DB state, exits 0/2, never itself
  owns persisted state. Serves issues 2, 3, 4 (tier resolution,
  plans-dir allow-list, `_oop_active()` rewrite and status-block
  reporting).
- **`state_db_class.py` / `state_db.py`** (existing, loose top-level
  module) — purpose: persist sprint/lock/recovery/OOP lifecycle state in
  SQLite. Boundary: owns the schema and all direct DB access; callers
  never touch SQLite directly. Serves issue 4 (new `oop_state` table
  and `set_oop`/`clear_oop`/`get_oop` methods, modeled on the existing
  `recovery_state` singleton-table pattern already in this module).
- **`cli.py`** (existing, loose top-level module) — purpose: expose
  CLASI operations as CLI commands. Boundary: thin command layer over
  `state_db`/`hook_handlers` functionality, no business logic of its
  own. Serves issue 4 (new `oop` command group, mirroring the existing
  `sprint` group's structure).
- **`.claude/agents/team-lead/agent.md`** (doc, not a module) — serves
  issue 1.
- **`tools/artifact_tools.py`** (existing subsystem module, per
  `tools/DESIGN.md`) — purpose: MCP tool functions over artifact and
  process operations. Boundary: the agent-facing tool surface; serves
  issue 5 (configurable `close_sprint` timeout).
- **Docs** (`_rules.py` generator sources, guard error strings, the
  `oop` plugin skill, this repo's on-disk `.claude/rules/*.md`) — serve
  issue 4's rewording requirement.

No new module is introduced by this sprint; every responsibility above
lands inside an existing module's boundary. This is itself a signal
against needing a component diagram: there is nothing new being
composed, only existing modules gaining a table, a method set, a CLI
group, and a few allow-list/config entries.

### Step 4: Diagrams

No diagrams. Every module touched already exists and already owns the
responsibility being extended (`hook_handlers.py` already dispatches
guard decisions and already has an `_oop_active()` single-result
point; `state_db_class.py` already hosts singleton-table state via
`recovery_state`; `cli.py` already hosts sibling command groups). The
one genuinely new element — the `oop_state` table — is a single
table with three scalar columns (`set_at`, `reason`, `expires_at`)
following an established in-module pattern; a component or ERD diagram
would show one box and one arrow already fully described in Step 3's
prose. This mirrors sprint 020's precedent: many modules touched for
independent fixes, no new cross-module composition worth diagramming.
The one new dependency this sprint does add —
`hook_handlers._oop_active()` reading through `state_db.get_oop()` —
is a single labeled edge between two already-adjacent modules (every
other guard-state read in `hook_handlers.py` already goes through
`state_db`), not a new subsystem relationship.

### Step 5: What Changed / Why / Impact / Migration Concerns

**What Changed**:
- `.claude/agents/team-lead/agent.md`: sprint-creation steps rewritten
  to dispatch sprint-planner instead of calling `create_sprint`
  directly; `link_sprint_issues` sequencing updated to recover the
  sprint id from the planner's report.
- `hook_handlers.py`: (a) tier-resolution instrumentation and, pending
  investigation findings, a fix to how `CLASI_AGENT_TIER` reaches
  `handle_role_guard`/`handle_mcp_guard` for sprint-planner dispatches;
  (b) `~/.claude/plans/` added to the tier-0 allow surface as an
  absolute-path comparison; (c) `_oop_active()` rewritten to check the
  DB (`state_db.get_oop()`) then the file, `_oop_source()` added for
  reporting, `handle_status_inject` changed to emit a minimal status
  block (never nothing) when OOP is active.
- `state_db_class.py` / `state_db.py`: new `oop_state` singleton table
  and `set_oop`/`clear_oop`/`get_oop` methods plus module-level
  wrappers.
- `cli.py`: new `oop` command group (`on`/`off`/`status`).
- `tools/artifact_tools.py`: `close_sprint`'s hardcoded `timeout=300`
  becomes a configurable parameter/config value with a higher default
  and the active value surfaced in the timeout error message.
- Docs: `_rules.py` generator bodies, guard error strings, the `oop`
  plugin skill, and this repo's regenerated `.claude/rules/*.md`
  reworded to document `clasi oop on/off/status` as primary with the
  flag file as the documented emergency path.

**Why**: each change closes a gap between a documented contract
(agent doc, guard behavior, bypass audit expectations, close-gate
timing) and what the code actually does — the recurring defect shape
across sprints 019-020 that this sprint is explicitly named to close
out.

**Impact on Existing Components**: additive in every case except the
`_oop_active()` rewrite, which changes bypass-resolution order (DB
checked; file remains the unconditional override checked first per
the stakeholder decision) and changes `handle_status_inject`'s
previously-silent behavior when OOP is active — existing tests
asserting the empty-output path (`tests/unit/test_status/
test_hook_injection.py`) must be updated to assert the new minimal
block, a known, called-out breaking test-assertion change, not a
breaking behavior change for any caller.

**Migration Concerns**: the `oop_state` table is `CREATE TABLE IF NOT
EXISTS`, auto-created on next `StateDB.init()` — no migration
machinery needed, consistent with every other table in this schema.
No backward-incompatible data change. The legacy `.clasi-oop` (hyphen)
file continues to be read (tolerate-on-read, per 019-002's contract) —
not removed by this sprint.

### Step 6: Design Rationale

**Decision: DB as primary OOP channel, file as unconditional
override, checked first.**
- **Context**: the OOP bypass currently has no audit trail and, before
  the out-of-process cwd fix, could silently fail to be found. The
  stakeholder decided (2026-07-16, recorded in issue 4) that the DB
  should be primary for auditability but the file must remain a working
  escape hatch even when the DB layer itself is broken.
- **Alternatives considered**: DB-only (rejected — a broken DB would
  remove the only escape from a broken guard, which is precisely the
  failure mode 020-002's fail-closed design was built to avoid);
  file-only status quo (rejected — no audit trail, the problem this
  issue exists to fix).
- **Why this choice**: the file's entire value is that it needs no
  working subsystem to function; checking it first (not merging/
  reconciling with the DB) preserves that property exactly. The DB
  adds reason/timestamp/TTL on top without weakening the escape.
- **Consequences**: divergence between DB and file state is possible
  (e.g., DB says active with reason X, file also present) and is
  reported loudly rather than silently reconciled, per the issue's
  explicit requirement — a user-visible status-block change, not a
  hidden internal one.

**Decision: global-to-checkout TTL scope, not per-session.**
- **Context**: per-session OOP scoping would be more precise but
  depends on session-identity plumbing that issue 2 is investigating
  as possibly broken or unwired.
- **Alternatives considered**: per-session scoping now (rejected —
  blocked on unverified plumbing this same sprint is investigating;
  building on top of an unverified mechanism risks a second silent
  no-op gate).
- **Why this choice**: ship the auditability improvement now on a
  mechanism (global TTL) that doesn't depend on the open question;
  revisit per-session scoping once issue 2's findings land.
- **Consequences**: two agents in the same checkout share one OOP
  state; documented as out of scope rather than silently assumed.

### Step 7: Open Questions

- Issue 2's own fix is contingent on its investigation findings — the
  ticket for it is written as instrument-then-decide, not a
  predetermined code change. Whether the `active_agents` DB fallback
  is kept, fixed, or deleted is an outcome of that ticket, not a
  premise of this architecture.
- Whether `CLASI_AGENT_TIER` wiring (once understood) requires a
  change to `.claude/settings.json` or dispatch scripts outside this
  sprint's named files is unknown until issue 2's ticket investigates;
  if it surfaces a fix outside this sprint's stated scope, that's a
  candidate for a follow-up issue rather than silently expanding this
  sprint.
- The exact default for `close_sprint`'s new timeout (issue 5 suggests
  900s or 0-for-unlimited) is a ticket-level implementation choice, not
  an architectural one — left to the ticket.

## Use Cases

Four sprint-level use cases, each parented to an existing project-level
use case in `docs/design/usecases.md` whose mechanism this sprint
corrects rather than replaces. No new top-level use case is introduced —
every issue here fixes a gap inside an existing documented flow.

### SUC-001: Team-lead creates a sprint through the documented, guard-consistent path
Parent: UC-002 (Execute TODOs Through a Full Sprint)

- **Actor**: Team Lead, Sprint Planner
- **Preconditions**: Team-lead has one or more issues ready to plan into
  a sprint.
- **Main Flow**:
  1. Team-lead dispatches sprint-planner with the title and issue
     references (no direct `create_sprint` call).
  2. Sprint-planner calls `create_sprint`, then reports the new sprint
     id back to team-lead.
  3. Team-lead calls `link_sprint_issues` using the reported id.
- **Postconditions**: Sprint created and issues linked, with no guard
  denial anywhere in the flow.
- **Acceptance Criteria**:
  - [ ] Walking this flow live as team-lead produces no
        `CLASI ROLE VIOLATION` denial at any step.
  - [ ] A guard test with a real captured tier-0 payload still asserts
        `create_sprint` is denied for team-lead (the fix aligns the
        doc to the guard, not the reverse).

### SUC-002: Sprint-planner tier resolution is verified end-to-end
Parent: UC-002 (Execute TODOs Through a Full Sprint) — specifically the
sprint-planner dispatch step within it.

- **Actor**: Sprint Planner, Team Lead (dispatcher)
- **Preconditions**: A sprint-planner is dispatched for planning work
  requiring a write under `clasi/sprints/**`.
- **Main Flow**:
  1. Team-lead dispatches sprint-planner (real dispatch, not a fixture).
  2. Instrumentation records the actual `CLASI_AGENT_TIER` value the
     process sees and which resolution branch `handle_role_guard` takes.
  3. Investigation explains the programmer (tier-2) / planner
     (never tier-1) asymmetry and determines whether the
     `active_agents` DB fallback is load-bearing or dead.
  4. Whatever the finding, a durable end-to-end test asserts a real
     dispatched sprint-planner can write `clasi/sprints/**` with no
     `.clasi/oop` set.
- **Postconditions**: The tier-1 branch is either confirmed live (and
  now covered by a real-dispatch test) or replaced with whatever
  mechanism the investigation shows actually governs sprint-planner
  writes — no longer an unverified assumption either way.
- **Acceptance Criteria**:
  - [ ] A dispatched sprint-planner writes a ticket file with no OOP
        flag: allowed, and the reason code in `hooks.log` is
        attributable and explained (whether that is `tier-1` or
        another verified path).
  - [ ] A dispatched programmer still resolves to `tier-2` (regression
        check — must not break).
  - [ ] Team-lead remains blocked from `clasi/sprints/**` and source
        writes (the fix must not make the unresolved case permissive).

### SUC-003: Team-lead can write the plan-mode plan file without a guard denial
Parent: UC-002 (Execute TODOs Through a Full Sprint) — the plan-to-issue
pipeline step.

- **Actor**: Team Lead
- **Preconditions**: Team-lead is in Claude Code plan mode, about to
  call `ExitPlanMode`.
- **Main Flow**:
  1. Team-lead writes the plan file to `~/.claude/plans/<name>.md`.
  2. `handle_role_guard` allow-lists that absolute path for tier 0.
  3. `ExitPlanMode` reads the file; clasi's `plan_to_issue` PostToolUse
     hook harvests it into `clasi/issues/`.
- **Postconditions**: Plan file written and converted to an issue with
  no guard denial and no Bash-heredoc workaround needed.
- **Acceptance Criteria**:
  - [ ] A tier-0 Write to `~/.claude/plans/test.md` passes the guard
        (exit 0).
  - [ ] A tier-0 Write to an arbitrary outside-root path (e.g.
        `~/Desktop/x.md`) is still blocked (exit 2) — the allow-list is
        narrow, not a general outside-root escape.
  - [ ] Unit tests use real captured hook payloads for both the allow
        and the deny case.

### SUC-004: OOP bypass state is auditable, TTL-bound, and loudly reported
Parent: UC-006 (Make an Out-of-Process Change)

- **Actor**: Stakeholder, any guard-checking hook handler
- **Preconditions**: Stakeholder wants to bypass CLASI enforcement for
  a session or a bounded period.
- **Main Flow**:
  1. Stakeholder runs `clasi oop on --reason '<why>'` (DB channel,
     default TTL 8 hours) or, when CLASI's own tooling is broken,
     touches `.clasi/oop` (file channel, unconditional, checked first).
  2. `_oop_active()` checks the file, then the DB, in that order;
     `_oop_source()` reports which (or both) fired.
  3. `handle_status_inject` includes a status-block line whenever OOP
     is active, naming source, age/reason, and expiry — never silent.
  4. `clasi oop off` clears the DB row and removes flag files.
  5. On read past `expires_at`, the DB row is deleted and a warning is
     emitted; enforcement resumes.
- **Postconditions**: Every active bypass is attributable (source,
  reason, age) and self-expiring; a broken DB never defeats the file
  escape.
- **Acceptance Criteria**:
  - [ ] `clasi oop on --reason test` → role-guard allows a source
        write (exit 0, reason `oop-bypass`); `clasi oop status` shows
        reason/age; the status block carries the OOP line; `clasi oop
        off` → guard blocks again (exit 2).
  - [ ] Cwd-independence: flag set at project root, hook invoked with
        cwd = a subdirectory — bypass still resolves (already fixed by
        `_find_project_root`, re-asserted here as a regression check,
        not re-implemented).
  - [ ] File override with DB empty: `touch .clasi/oop` → bypass
        works; status block reports "override file, no audit record".
  - [ ] `clasi oop on --ttl-hours 0.0001` → row auto-expires on next
        read; enforcement resumes.
  - [ ] Handler-level tests cover the DB flag on both `role-guard` and
        `mcp-guard` (helper-level tests alone are insufficient, per the
        019-002 lesson).
  - [ ] Corrupt/locked DB file: file override still works, no
        exception raised.

### SUC-005: Closing a sprint runs the real test suite without a false timeout
Parent: UC-005 (Close a Completed Sprint)

- **Actor**: Team Lead (or any operator running `close_sprint`)
- **Preconditions**: A sprint's tickets are all done and ready to close.
- **Main Flow**:
  1. Operator calls `close_sprint` with the default (or an explicit)
     test command.
  2. The test-suite timeout is read from a configurable value (default
     raised to fit a real suite, e.g. 900s, or unlimited at 0) rather
     than the previous hardcoded 300s.
  3. Test suite runs to completion; close proceeds on success.
- **Postconditions**: A healthy suite that takes longer than 300s but
  less than the configured timeout completes the `tests` step instead
  of being falsely reported as timed out.
- **Acceptance Criteria**:
  - [ ] Closing a sprint in this repo with the default `uv run pytest`
        completes the `tests` step (given the suite passes) without a
        timeout.
  - [ ] A deliberately-hung test still trips the now-configurable
        timeout and blocks the close.
  - [ ] The timeout value in effect is surfaced in the error message
        when a timeout does occur.

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
| 001 | Align team-lead sprint-creation flow with mcp-guard's tier-0 block | — |
| 002 | Instrument and verify sprint-planner tier (CLASI_AGENT_TIER) wiring end-to-end | — |
| 003 | Allow-list ~/.claude/plans/ in role-guard for tier 0 | — |
| 004 | OOP state: oop_state DB table + StateDB methods | — |
| 005 | _oop_active() DB-aware rewrite + status-block reporting | 004 |
| 006 | clasi oop CLI group + docs rewording | 004 |
| 007 | Make close_sprint's test timeout configurable | — |

Tickets execute serially in the order listed.
