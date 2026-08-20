---
status: done
sprint: '026'
tickets:
- 026-006
---

# Programmer sub-agents stall on background pytest and orphan their terminal work

Source reflection: `radio-robot-elite/clasi/reflections/2026-07-16-programmer-agents-stall-on-background-pytest.md` (sprint 108 + an OOP follow-up in that project).

## Failure mode

Roughly 6 times in one session, a dispatched **programmer sub-agent** finished its code edits, launched the full test suite (`uv run python -m pytest`, about 4-5 min) as a **background/detached task**, and then **ended its turn** with the work uncommitted and the ticket not marked done — reporting "standing by for the background pytest to complete." It never resumed. Each time the team-lead had to take over: run the suite in its own context and commit the sub-agent's work — defeating the point of delegation.

## Root cause

A sub-agent that spawns a background task and has no remaining foreground tool call has its turn ended by the harness. The **main loop** is re-invoked when a background bash task completes; a **sub-agent apparently is not reliably resumed** the same way. The completion fires, but the agent has already stopped, so its terminal work (commit, mark ticket done, final report) is silently orphaned.

## Contributing factors

1. The target project's suite is slow (~4-5 min — C++ harness tests recompile from scratch per test), making backgrounding tempting.
2. `run_in_background` is an available affordance; agents reach for it for anything long, unaware it is a trap inside a sub-agent.
3. Every programmer runs the FULL suite redundantly (N tickets × ~5 min) instead of a scoped subset.
4. Prompt-level mitigation ("run FOREGROUND, do not background") in dispatch prompts helped but did not fully stop it — habit/affordance won.

## Proposed fixes (ranked, from the reflection)

1. **Programmer agent definition** (`.claude/agents/programmer/*`): hard rule — never background the test run; run it synchronously so the agent stays alive to see the result and finish. A ticket is not done until committed. Programmers run only the tests relevant to their ticket.
2. **Split the test gate:** programmers run a scoped subset; the team-lead / execute-sprint runs the full suite **once** before close. Removes both the redundancy and the per-agent stall temptation.
3. **Enforcement (CLASI-level):** consider a PreToolUse-style gate that blocks `run_in_background: true` Bash calls for programmer-tier agents, since prompt guidance alone has proven insufficient (consistent with the fail-open-gates lesson: enforce, don't advise).
4. **Harness-level (upstream, out of CLASI's control but worth documenting):** either block `run_in_background` inside sub-agents or guarantee sub-agent re-invocation when their background task completes. Until then CLASI must treat sub-agent backgrounding as forbidden.

## Acceptance sketch

- Programmer agent definition contains the no-background / scoped-tests rules.
- execute-sprint (or close gate) owns the single full-suite run.
- Optionally: a guard hook denies `run_in_background` from programmer dispatches, with a test asserting the deny path using a real captured payload.
