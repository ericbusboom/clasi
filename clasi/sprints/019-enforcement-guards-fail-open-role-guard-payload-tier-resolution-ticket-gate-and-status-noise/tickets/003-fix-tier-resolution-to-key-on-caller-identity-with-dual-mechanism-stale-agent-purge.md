---
id: '003'
title: Fix tier resolution to key on caller identity, with dual-mechanism stale-agent
  purge
status: open
use-cases: [SUC-003]
depends-on: ['001']
github-issue: ''
issue: enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix tier resolution to key on caller identity, with dual-mechanism stale-agent purge

## Description

`StateDB.get_active_tier` (`src/clasi/state_db_class.py:643`) runs
`SELECT tier FROM active_agents LIMIT 1` with no `WHERE agent_id = ?`
and no ordering. It answers "what tier is *somebody*?" instead of "what
tier is the *caller*?" — with concurrent agents (normal for this
project), the result is arbitrary. This is compounded by unbounded
accumulation: `active_agents` never gets cleaned up in normal operation
(`clear_stale_agents`, a 24h TTL sweep, exists but is never called).

This ticket has two parts:

**Part A — key the lookup on caller identity.** Change
`get_active_tier` to accept an `agent_id` parameter and query
`WHERE agent_id = ?`. Thread the calling agent's identity through from
the hook payload (`agent_id` or `session_id`, whichever the payload
provides — `handle_role_guard` and `handle_mcp_guard` currently discard
this) to the `get_active_tier` call site in `hook_handlers.py`. If no row
matches the caller's identity, the tier is unresolvable: return the
existing "unresolved" sentinel (empty string) rather than any other
agent's tier — callers already fail closed on an empty-string tier per
ticket 001/existing role-guard logic (tier 0/1 blocked from source
writes).

**Part B — dual-mechanism purge**, so ghosts stop accumulating in the
first place:
- Primary: `handle_subagent_stop` reliably calls `remove_active_agent`
  for the stopping agent (verify this already happens correctly — the
  existing code path removes by `marker_id`; confirm no code path skips
  it on early return).
- Backstop: call `clear_stale_agents` from a cheap, frequently-hit path
  (`handle_subagent_start` is the natural choice — it already touches
  the DB on every subagent dispatch). Lower the TTL well below the
  current 24h default — a 24-hour-old "active" agent is not a real thing
  in this project's operating cadence; pick a TTL on the order of
  minutes-to-low-hours and document the choice in the ticket's
  implementation notes.

**Do NOT assume `active_agents` currently has stale rows** — the table in
this repo was manually cleared during triage before this sprint was
planned and is empty as of sprint start. Tests must create their own
fixture rows (including artificially-aged ones, by inserting rows with a
backdated `started_at`, for the TTL-sweep test) rather than relying on
any pre-existing state.

Depends on ticket 001 because both tickets modify the same
`handle_role_guard`/`handle_mcp_guard` call sites (001 for payload
parsing, this ticket for the `agent_id` threading) — sequencing avoids
overlapping edits within the sprint's serial execution.

Root cause reference: `clasi/issues/enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md`
defect 3 (arbitrary tier resolution) and its "no cleanup" compounding
factor.

## Acceptance Criteria

- [ ] `StateDB.get_active_tier(agent_id: str) -> str` queries
      `WHERE agent_id = ?` (or equivalent parameterized lookup) instead
      of `LIMIT 1` with no filter.
- [ ] Returns the existing "unresolved" sentinel (empty string) when no
      row matches — never another agent's tier, under any circumstance.
- [ ] `hook_handlers.py` call sites (`handle_role_guard`,
      `handle_mcp_guard`) thread the payload's `agent_id` (falling back
      to `session_id` if `agent_id` is absent) into the
      `get_active_tier` call.
- [ ] **Concurrent-registration test** (non-negotiable — a single-agent
      test passes trivially and would not have caught the original bug):
      register two agents with different tiers in `active_agents`
      simultaneously (e.g. tier "1" and tier "2"), then assert that a
      caller identified by each agent's own `agent_id` gets back that
      agent's own tier — not the other's, not whichever row happens to
      sort first.
- [ ] Test: caller `agent_id` has no matching row and no `CLASI_AGENT_TIER`
      env var set → tier resolves to the unresolved sentinel, and
      `handle_role_guard` fails closed for that caller at tier 0/1
      (reusing ticket 001's fail-closed behavior).
- [ ] `handle_subagent_stop` is confirmed (by test, not just inspection)
      to remove the agent's `active_agents` row on every normal stop
      path, including when `last_message`/`transcript_path` are empty.
- [ ] `clear_stale_agents` is actually invoked from `handle_subagent_start`
      (or another frequently-hit path — implementer's call, document
      which) with a TTL well below the previous 24h default.
- [ ] Test: a row with an artificially backdated `started_at` (older
      than the new TTL) is purged the next time the sweep-invoking path
      runs; a row within the TTL window is NOT purged.
- [ ] No test in this ticket assumes `active_agents` has pre-existing
      stale rows — every test creates its own fixture data.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_hook_handlers.py tests/unit/test_state_db*.py -v`
- **New tests to write**: concurrent-registration tier-resolution test;
  unresolved-tier fail-closed test; `SubagentStop` unregister test;
  TTL-sweep purge test (both purged-because-stale and
  kept-because-fresh cases).
- **Verification command**: `uv run pytest tests/unit/test_hook_handlers.py tests/unit/test_state_db*.py -v`
