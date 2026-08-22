---
status: pending
type: bug
tags:
- oop
- enforcement
- e2e-finding
---

# The OOP bypass is not reliably cleared after an out-of-process change

## Description

Found by the full multi-sprint E2E run `20260821-152013-39582` (2026-08-21).
The run made the three scripted OOP changes. The bypass flag was handled
inconsistently across them:

| Beat | Outcome |
|---|---|
| M2 — title-case (master, no sprint) | left **active**; needed a stakeholder nudge to clear |
| M4 — `__version__` (sprint open) | cleared **unprompted** |
| M5 — TODO comment (master, no sprint) | left **active** again |

So it is not a knowledge gap and not learned behavior — it is inconsistent.

Note on attribution: M2's first attempt hit `error_max_turns` (the tester
under-budgeted at 14 turns), so that one is not evidence. But the M2 *resume*
turn completed cleanly after an explicit "finish whatever's left to tidy up and
confirm we're clean" and still left the flag on, and M5 completed cleanly and
left it on. Those two are the evidence.

## Why it matters more than tidiness

An active OOP flag **silently voids every guard** for its lifetime. Within this
run it meant the remaining sprints would have executed with enforcement
bypassed — the guard behaviour the E2E exists to exercise would not have been
exercised at all, and nothing would have said so.

The 7-hour TTL from the db-backed-OOP work bounds cross-session damage, which is
real progress. It does nothing within a session, which is where sprints happen.

## Why this should be enforced rather than remembered

Three sprints of this campaign were spent removing "the agent has to remember
to do X" from the process. This is the same shape. Options, roughly in order of
preference:

1. **Auto-clear on completion.** The OOP flag exists to permit a specific
   change; clear it when that change is committed. A `--reason`-scoped bypass
   that survives its own commit is broader than its stated purpose.
2. **Make it loud while active.** The status block already reports OOP state;
   make it a prominent warning rather than a line, so the next turn cannot
   miss it. (Cheap, but still relies on someone acting on it.)
3. **Shorten the default TTL substantially** for the common case, with the long
   TTL available explicitly for a genuinely long bypass.

Option 1 is the only one that removes the human step.

## Acceptance criteria

- [ ] Completing an OOP change leaves the bypass inactive without anyone
      remembering to run `clasi oop off`.
- [ ] A deliberately long-running bypass is still possible when explicitly
      requested — this must not make OOP unusable for multi-step work.
- [ ] `clasi oop status` remains the single source of truth, and the file-based
      emergency override is unaffected.
- [ ] A test covers the auto-clear path, including that a *failed* OOP change
      does not silently clear the flag and strand the work.
