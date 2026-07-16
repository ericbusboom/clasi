---
status: pending
type: bug
tags:
- enforcement
- guards
- agents
- state-db
---

# Subagent registration never fires: active_agents is always empty, so every subagent resolves to tier 0

## Description

`role-guard` resolves a caller's tier by looking up `active_agents` in the state
DB. That table is **empty** — verified live on 2026-07-16 during sprint 020:

```
columns: ['agent_id', 'agent_type', 'tier', 'log_file', 'started_at']
active agents: 0
```

With no row, `get_active_tier()` returns the unresolved sentinel (empty string)
and the caller falls through to tier 0's rules. Every subagent is therefore
treated as team-lead regardless of what it actually is.

**Observed consequence**: a sprint-planner dispatched to update a ticket file was
blocked by role-guard with `CLASI ROLE VIOLATION: team-lead (tier 1) attempted
direct file write to: clasi/sprints/020-.../tickets/002-....md`. But
`hook_handlers.py:357-359` explicitly permits exactly this:

```python
_sprints_prefix = _block_prefixes[0]
if agent_tier == "1" and file_path.startswith(_sprints_prefix):
    _exit_hook("role-guard", payload, 0, "tier-1")
```

The rule is correct. The identity never arrives, so the rule never applies. The
sprint-planner correctly threw an exception rather than routing around the guard
via Bash, which left the sprint deadlocked: team-lead is blocked from ticket
artifacts (correctly), and the agent that *should* own them is blocked too
(incorrectly). Work only proceeded under `.clasi/oop`.

This is a **fail-closed-in-the-wrong-direction** defect and the mirror image of
what sprint 019 fixed. 019 made the guards stop failing open; this makes them
over-block the one role that has legitimate write scope.

## Cause

Not yet root-caused. The registration path is `handle_subagent_start` →
`register_active_agent(...)` in `hook_handlers.py`, wired to the `SubagentStart`
hook in `.claude/settings.json`. One of the following is true:

1. The `SubagentStart` hook is not firing at all for dispatched agents.
2. It fires but `register_active_agent` isn't reached (early return, exception
   swallowed).
3. It writes to a different DB path than the one `get_active_tier` reads.
4. The row is written and then immediately purged — note `019-003` added a
   `clear_stale_agents(ttl_hours=2)` sweep to `handle_subagent_start` itself.
   **Check this first**: if the sweep's TTL comparison is wrong (e.g. timezone
   or units), it could purge the row it just wrote, or purge on every start.

Start by instrumenting: dispatch any subagent and check whether the row appears
in `active_agents` at all, then whether it survives.

## Why this survived 019

Sprint `019-003` fixed `get_active_tier` to key on caller identity
(`WHERE agent_id = ?` instead of `LIMIT 1`). Its tests — including the
non-negotiable concurrent-registration test — pass because they **insert their
own fixture rows** via `db.register_active_agent(...)` and then query them back.
The lookup is correct and well-tested. Nothing ever asserted that a *real
dispatch* produces a row.

That is precisely the gap this sprint keeps rediscovering: a test that exercises
the function under test but not the path that feeds it. See also `019-001`
(role-guard never fired for months because the payload parse was wrong while its
tests hand-built the payload) and `019-007` (three tests asserted the archive
writer's buggy output as the contract).

## Proposed fix

1. Root-cause which of the four causes above applies (instrument, don't guess).
2. Fix the registration path.
3. **Add an end-to-end test that dispatches a real subagent and asserts a row
   lands in `active_agents` with the right tier** — not a fixture insert. This
   is the test whose absence allowed the defect, and it is the only one that
   matters here.
4. Re-verify `019-003`'s tier resolution end-to-end, since its correctness has
   never actually been exercised against a real registration.

## Verification

- Dispatch a sprint-planner; assert `active_agents` gains a row with `tier=1`.
- That planner can write `clasi/sprints/**` without `.clasi/oop`.
- Dispatch a programmer; assert `tier=2`, and that it can write source.
- Team-lead (no row) still resolves to tier 0 and is still blocked from both —
  the fix must not make the unresolved case permissive.
- The `clear_stale_agents` sweep does not purge a row younger than its TTL.

## Related

- Blocked sprint 020 mid-execution; `020-002`'s completion notes record the
  full incident.
- `019-003` fixed the tier lookup and added the dual-mechanism purge; its
  fixture-row tests are why this wasn't caught.
- `019-002` gave `.clasi/oop` a single source of truth — which is the only
  reason there was a usable escape hatch when this deadlocked.
