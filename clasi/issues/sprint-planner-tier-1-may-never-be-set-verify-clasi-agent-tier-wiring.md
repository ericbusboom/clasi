---
status: pending
type: bug
tags:
- enforcement
- guards
- agents
- sprint-planner
---

# Sprint-planner tier-1 may never be set: verify CLASI_AGENT_TIER wiring end-to-end

## Description

**Read this before acting: the headline symptom that prompted this issue has
already been fixed. What remains is an unverified assumption.**

On 2026-07-16 a dispatched sprint-planner was blocked from writing a ticket file
under `clasi/sprints/` — its own declared write scope — deadlocking sprint 020.
The root cause turned out to be path normalization, not tier resolution:
`handle_role_guard` compared Claude Code's **absolute** `file_path` against
root-relative prefixes, so `startswith()` never matched for anyone. Fixed during
sprint 020 (`_normalize_to_root_relative`, `hook_handlers.py`), and verified live:

```
tier 1 + ABSOLUTE clasi/sprints/... → exit 0   (was exit 2 — the deadlock)
```

So the tier-1 branch at `hook_handlers.py` now works **when `CLASI_AGENT_TIER=1`
is actually set**.

**The open question**: is it ever set for a real sprint-planner dispatch?

The programmer who fixed the normalization grepped and found no wiring in
`.claude/settings.json` or any hook that exports `CLASI_AGENT_TIER` per agent
type. It is only ever *read* — from the environment, or via the DB-backed
`get_active_tier()` fallback. Meanwhile:

- `active_agents` is empty (verified: 0 rows), so the DB fallback resolves
  nobody.
- Yet programmers demonstrably reach tier 2. From `.clasi/log/hooks.log`, 22
  calls resolved to reason `tier-2` with `agent_type=programmer`. Something sets
  it for them.
- The sprint-planner has never once resolved to reason `tier-1` in the log.

That asymmetry is unexplained. Either the harness sets the env var for some agent
types and not others, or tier 2 is arriving by a path nobody has traced.

## Why this is worth chasing even though the deadlock is fixed

If `CLASI_AGENT_TIER` is never `"1"` in practice, then the tier-1 allow branch is
dead code that merely *looks* correct, and sprint-planners are passing role-guard
today only because their writes happen to land on paths tier 0 also allows. The
next time a planner needs `clasi/sprints/`, it deadlocks again — and the fix
above will make that look impossible, which is worse than an obvious failure.

This is the same shape as the defects sprints 019-020 kept finding: a guard whose
rule is right, whose plumbing is untested, and whose tests supply the input the
production path never does.

## Investigation steps

1. **Instrument, do not guess.** Dispatch one of each agent type and log the
   actual `CLASI_AGENT_TIER` value each process sees, plus which resolution
   branch `handle_role_guard` takes.
2. Explain the programmer/planner asymmetry specifically. Why does
   `agent_type=programmer` reach `tier-2` while `agent_type=sprint-planner` never
   reaches `tier-1`?
3. Determine whether the `active_agents` DB fallback is load-bearing or dead. It
   currently resolves nobody (0 rows). If it is meant to work, registration is
   broken — check whether `019-003`'s `clear_stale_agents(ttl_hours=2)` sweep
   inside `handle_subagent_start` purges rows it just wrote. If the env var is
   the real mechanism, say so and consider deleting the fallback rather than
   leaving a path that silently never fires.

## Proposed fix

Depends on the investigation. Whatever the outcome:

**Add an end-to-end test that dispatches a real sprint-planner and asserts it can
write `clasi/sprints/**` without `.clasi/oop`** — not a fixture insert, not a
hand-set env var. That is the test whose absence allowed this, and the only one
that proves the plumbing.

`019-003` fixed `get_active_tier` to key on caller identity and tested it
thoroughly, including a non-negotiable concurrent-registration test. Every one of
those tests inserts its own rows via `db.register_active_agent(...)` and queries
them back. The lookup is correct. Nothing asserted that a real dispatch produces
a row.

## Verification

- A dispatched sprint-planner writes a ticket file with no OOP flag: allowed,
  and `hooks.log` shows reason `tier-1` — a code that has never appeared.
- A dispatched programmer still writes source: reason `tier-2` (regression; works
  today, must not break).
- Team-lead still blocked from `clasi/sprints/**` and source: the fix must not
  make the unresolved case permissive.

## Related

- Deadlocked sprint 020; `020-002`'s completion notes record the incident.
- The path-normalization fix that resolved the *symptom* landed in sprint 020 as
  an unplanned fix during ticket 003, with an absolute/relative parametrized test
  suite and a verified revert-check.
- `019-002` gave `.clasi/oop` a single source of truth — the only reason there was
  a usable escape hatch when this deadlocked.
- Supersedes `subagent-registration-never-fires-active-agents-always-empty.md`,
  which claimed *all* subagents resolve to tier 0. That was wrong: programmers
  resolve to tier 2 correctly. Delete that file in favour of this one.
