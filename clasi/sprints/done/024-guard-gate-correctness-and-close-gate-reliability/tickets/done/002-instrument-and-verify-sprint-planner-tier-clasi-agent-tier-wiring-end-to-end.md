---
id: '002'
title: Instrument and verify sprint-planner tier (CLASI_AGENT_TIER) wiring end-to-end
status: done
use-cases:
- SUC-002
depends-on: []
github-issue: ''
issue: sprint-planner-tier-1-may-never-be-set-verify-clasi-agent-tier-wiring.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Instrument and verify sprint-planner tier (CLASI_AGENT_TIER) wiring end-to-end

## Description

It is unverified whether `CLASI_AGENT_TIER=1` is ever actually set for a
real sprint-planner dispatch. Programmers reliably resolve to `tier-2` in
the hooks log, but sprint-planner has never once resolved to reason
`tier-1` — meaning the role-guard's tier-1 branch may be dead code, and
whatever currently allows sprint-planner to write `clasi/sprints/**` may be
resolving through an unintended or unverified path (e.g. the `active_agents`
DB fallback, or an unrelated allow rule).

This is investigation-first work, per the issue's own "Investigation
steps" section: instrument real dispatches to observe actual behavior
before deciding on a fix. Do not assume the fix is "set
`CLASI_AGENT_TIER=1` somewhere" — the instrumentation may show the
`active_agents` DB fallback is the actual load-bearing mechanism, in which
case the fix is different (and the env var may be dead in the other
direction).

## Acceptance Criteria

- [x] A dispatched sprint-planner writes a ticket file with no `.clasi/oop`
      set: the write is allowed, and the reason code recorded in
      `hooks.log` is identified and explained (whether that is `tier-1`,
      an `active_agents` DB fallback reason, or another path).
      **Finding**: reason is `tier-1`, resolved entirely through the
      `active_agents` DB fallback (`get_active_tier`) — see Investigation
      Findings below.
- [x] The programmer (tier-2) / sprint-planner (never tier-1) asymmetry is
      explained: what causes programmer dispatches to reliably set
      `CLASI_AGENT_TIER=2` while sprint-planner dispatches apparently never
      set `CLASI_AGENT_TIER=1` the same way.
      **Finding**: there is no asymmetry in the resolution mechanism.
      Neither agent type ever gets `CLASI_AGENT_TIER` set as an env var —
      grep of the whole repo (`.claude/settings.json`, all hook scripts,
      `hook_handlers.py`, `mcp_server.py`) shows it is read-only, never
      assigned. Both agent types resolve identically through
      `handle_subagent_start`'s `_AGENT_TYPE_TIERS` map ->
      `register_active_agent` -> `get_active_tier` DB lookup in the guard
      handlers. The issue's "sprint-planner never resolves tier-1"
      observation does not hold today: this repo's own live
      `.clasi/log/hooks.log` already contains many
      `role-guard 0 tier-1 ... agent_type=sprint-planner` lines from
      earlier in this same session, before any code in this ticket was
      touched.
- [x] It is determined, with evidence (not inference), whether the
      `active_agents` DB fallback (`get_active_tier`) is load-bearing for
      any real dispatch path or is dead code (the issue notes it currently
      has 0 rows).
      **Finding**: load-bearing, not dead. It is the *only* mechanism that
      resolves tier for either agent type (see above). The "0 rows"
      observation was a stale point-in-time snapshot, not a structural
      property — `active_agents` had 1 live row (this ticket's own
      programmer dispatch, tier 2) when checked during this
      investigation, and the new end-to-end test proves a fresh
      registration is written and read back correctly for both tiers.
- [x] A dispatched programmer still resolves to `tier-2` (regression
      check — the investigation and any resulting fix must not break the
      already-working programmer path).
      Covered by
      `TestRealDispatchTierResolutionEndToEnd::test_dispatched_programmer_still_resolves_tier2_regression`.
- [x] Team-lead remains blocked from `clasi/sprints/**` and source-code
      writes after this ticket lands (the fix must not make the
      previously-unresolved case permissive for team-lead).
      Covered by
      `TestRealDispatchTierResolutionEndToEnd::test_team_lead_no_dispatch_remains_blocked_from_sprints_and_source`.
- [x] A durable end-to-end test is added: a real dispatched sprint-planner
      (not a fixture insert, not a hand-set env var in a unit test) writes
      under `clasi/sprints/**` with no `.clasi/oop` present, and the test
      asserts the specific reason code that appears in `hooks.log` for
      that write.
      Added
      `TestRealDispatchTierResolutionEndToEnd::test_dispatched_sprint_planner_resolves_tier1_and_writes_sprints_dir`
      in `tests/unit/test_hook_handlers.py` — calls `handle_subagent_start`
      with a real `SubagentStart`-shaped payload (not
      `register_active_agent()` called directly), then `handle_role_guard`
      with a payload sharing the same `agent_id`, and asserts both the
      exit code and the literal `hooks.log` line containing `0 tier-1`.

## Outcome (no code fix required)

This ticket was investigation-first per its own plan, and the
investigation concluded **no fix to `hook_handlers.py` or
`state_db_class.py` is needed**: the tier-resolution mechanism (DB
fallback via `active_agents` / `get_active_tier`) already works
correctly and symmetrically for both `sprint-planner` and `programmer`
dispatches, confirmed by a new real-dispatch-pipeline test (not a
fixture insert). `CLASI_AGENT_TIER` is dead in the sense that nothing
in this repo ever sets it as an env var — the DB fallback is the
actual, sole, working mechanism, and it was already fine for both
agent types. The gap the issue correctly identified was a **test
coverage gap** (no test exercised `handle_subagent_start`'s real
registration path together with the guard's read path — every
existing test inserted its own row via `register_active_agent()`
directly), not a functional defect in the tier-resolution code
itself. That gap is now closed by
`TestRealDispatchTierResolutionEndToEnd` in
`tests/unit/test_hook_handlers.py`.

## Implementation Plan

**Approach**: Instrument first, fix second, per the issue's own
investigation steps.

1. Add temporary (or permanent, if useful for future debugging)
   instrumentation logging the actual `CLASI_AGENT_TIER` env var value and
   which branch of `handle_role_guard` / `handle_mcp_guard` fires, at the
   point those handlers make their allow/deny decision.
2. Perform a real sprint-planner dispatch (not a simulated one) and
   capture the hooks.log output for its writes under `clasi/sprints/**`.
3. Compare against a real programmer dispatch's hooks.log output for its
   writes, to characterize the asymmetry.
4. Inspect `active_agents` table state (via `StateDB`) before and after
   each dispatch to determine whether `get_active_tier`'s fallback path is
   ever actually consulted or ever returns a non-empty result.
5. Based on findings, implement whichever fix is warranted: correcting
   `CLASI_AGENT_TIER` wiring at the dispatch site so sprint-planner reaches
   tier-1 as intended, or removing/documenting the `active_agents` fallback
   as dead code if it is confirmed unused, or documenting why the current
   (working, whatever it is) mechanism is sufficient without change if
   investigation shows sprint-planner writes are already correctly gated
   through a different verified path.
6. Add the end-to-end test specified in the acceptance criteria.

**Files likely to be read/modified** (exact scope depends on findings):
- `src/clasi/hook_handlers.py` — tier-resolution logic in
  `handle_role_guard` / `handle_mcp_guard`.
- Dispatch wiring for sprint-planner (wherever `CLASI_AGENT_TIER` is set
  for a sub-agent dispatch — likely `.claude/agents/sprint-planner/` config
  or the team-lead dispatch mechanism).
- `state_db_class.py` / `state_db.py` — `active_agents` table and
  `get_active_tier`, if findings implicate it.

**Testing plan**:
- New end-to-end test: real dispatched sprint-planner writes under
  `clasi/sprints/**`, no `.clasi/oop`, asserting the specific `hooks.log`
  reason code (not just "exit 0").
- Regression test: real (or equivalently faithful) dispatched programmer
  still resolves to `tier-2` and is still allowed to write its expected
  paths.
- Regression test: team-lead dispatch is still denied for
  `clasi/sprints/**` and source-code writes.
- If the `active_agents` fallback is found dead, add a test documenting
  that finding (e.g. asserting the table stays empty across a real
  dispatch, or removing the fallback code path with a test proving nothing
  regresses).

**Documentation updates**:
- Record the investigation's findings (asymmetry explanation, fallback
  live/dead determination) in this ticket or in a follow-up note referenced
  from it, so the reasoning is not lost after the ticket is closed.
- If `.claude/settings.json` or dispatch scripts outside this sprint's
  named files need a change to fully resolve the wiring, do not silently
  expand scope — note it as a candidate follow-up issue instead (per
  sprint.md's Open Questions).
