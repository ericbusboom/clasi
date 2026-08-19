---
id: '001'
title: 'role-guard consolidated hardening: tier-1 allow list, ticket-gate scope, recovery-path
  matching, per-invocation caching, block-message identity'
status: open
use-cases: [SUC-004, SUC-006, SUC-007, SUC-008]
depends-on: []
github-issue: ''
issue:
- hook-overhead-status-inject-dead-hooks-and-logging.md
- guard-dead-ends-no-ticket-gate-scope-and-close-sprint-recovery.md
- role-guard-tier1-design-dir-and-initiation-skill-hardcoded-path.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# role-guard consolidated hardening: tier-1 allow list, ticket-gate scope, recovery-path matching, per-invocation caching, block-message identity

## Description

Consolidate all planned edits to `handle_role_guard`
(`src/clasi/hook_handlers.py`) into one ticket, since three of this
sprint's four issues touch that single function and serializing three
separate tickets against the same function body would add merge risk
without real parallelism gain (see sprint.md's Design Rationale). This
ticket:

1. Extends the `_allow_prefixes` (design/issues/reflections/clasi-state/
   log) check to tier 1, matching the function's own documented matrix
   (currently only tier 0 consults it; tier 1's only allowance is the
   sprints prefix).
2. Scopes the ticket-state gate to tier 2 only, and exempts `issues_dir`/
   `reflections_dir` from the gate for every tier (stakeholder-decided
   2026-08-19, recorded in the source issue).
3. Makes the recovery-state lookup match directory-prefix entries in
   `allowed_paths`, not just exact-path equality (normalize entries; a
   trailing-slash or is-dir entry matches any file under it).
4. Resolves the block message's agent name from `get_active_agent`
   (state DB) when the tier itself was resolved from the DB, instead of
   falling back to the `CLASI_AGENT_NAME` env default.
5. Reuses a single `Project` instance, its parsed config, and one sqlite
   connection across every check within one `handle_role_guard`
   invocation, instead of calling `get_project()` (currently 5x),
   parsing `config.yaml` (currently 3x, `Project._load_config` has no
   cache), and opening a fresh sqlite connection (currently 4x) at each
   check site.

## Acceptance Criteria

- [ ] Tier 1 + write to configured `design_dir` (or issues/reflections/
      clasi-state/log dirs) → allowed, reason `artifact-dir`.
- [ ] Tier 1 + write to a source/test path → still blocked, reason
      `blk-write` (docstring matrix and implementation now agree).
- [ ] Execution lock held, zero tickets in-progress, tier-2 source write
      → blocked, reason `no-ticket` (unchanged).
- [ ] Same state, tier-0/1 write to an allow-listed path → allowed (no
      longer gated by ticket-state).
- [ ] Same state, any tier, write under `issues_dir` or `reflections_dir`
      → allowed (never gated by ticket-state).
- [ ] Recovery record containing a directory entry (e.g.
      `str(project.design_dir)`) → a file write under that directory
      passes with reason `recovery`; existing exact-path entries still
      match exactly (no regression).
- [ ] Block message names the DB-registered agent (via `get_active_agent`)
      when tier was resolved from the DB, not the `CLASI_AGENT_NAME` env
      default.
- [ ] `get_project()` call count within one `handle_role_guard`
      invocation drops from about 5 to 1; config parsed once, not 3x;
      one sqlite connection opened, not 4 (verified via a debug counter
      or mock call-count assertion).
- [ ] `time clasi hook role-guard < captured-payload.json` shows the
      startup-floor savings consistent with the reduced call counts
      above.
- [ ] Regression tests use real captured hook payloads (not synthetic)
      and assert both the allow path and the deny path for every
      condition above. No existing deny-path assertion is weakened.
- [ ] Scenario test: `throw_ticket_exception` → a dispatched
      sprint-planner can edit the sprint's architecture without OOP
      (exercises the ticket-gate scoping end-to-end).

## Implementation Plan

**Approach**: Edit `handle_role_guard` in place. Land the tier-1
allow-list extension and ticket-gate scoping first (pure gate-logic
changes), then the recovery-path directory-prefix matching, then the
block-message identity fix, then wrap the function's `get_project()`/
config/sqlite access points in a single per-invocation cache (e.g. a
local variable computed once at function entry and threaded through, or
an `lru_cache`-backed helper scoped to the call). Keep each change as a
separable diff within the same commit so a reviewer can trace which
lines serve which of the three source issues.

**Files to modify**:
- `src/clasi/hook_handlers.py` (`handle_role_guard`, its
  `_allow_prefixes`/`_block_prefixes` construction, the ticket-state
  gate block, the recovery-state lookup, the final block message).
- `tests/unit/test_hook_handlers.py` (or wherever role-guard's existing
  test module lives) — extend with real captured payloads for every
  allow/deny condition above.

**Testing plan**: Use real captured hook payloads (this repo's own
`.clasi/log/hooks.log` and prior test fixtures are good sources) for
every new assertion — synthetic payloads previously masked payload-shape
bugs in this exact function (see `hooks.log`'s empty `file_path` history).
Run the full existing `test_hook_handlers.py` suite to confirm no
existing deny-path test regresses.

**Documentation updates**: This sprint's `design/` overlay
(`clasi/sprints/026-hook-performance-and-guard-reliability/design/DESIGN.md`)
already describes these changes at the module level; no further doc
update is required beyond what ticket 026 planning already seeded.
