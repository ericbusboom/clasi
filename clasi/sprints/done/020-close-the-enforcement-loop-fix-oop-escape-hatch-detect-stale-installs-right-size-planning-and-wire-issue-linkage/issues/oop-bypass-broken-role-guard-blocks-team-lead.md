---
status: in-progress
type: bug
source: e2e-test-run-003
clasi_version: 0.20260715.2
tags:
- enforcement
- oop
- guards
- e2e
sprint: '020'
tickets:
- 020-001
---

# OOP bypass is broken: role-guard blocks team-lead from out-of-process edits

## Description

Sprint 019 fixed enforcement guards — they no longer fail open. But the OOP (out-of-process) bypass mechanism that's supposed to let agents make quick edits without sprint ceremony **does not work**. Team-lead agents are blocked from editing source files even when explicitly operating out-of-process.

## Evidence

From e2e test run 003 (guessing-game CLI, 4 sprints, 3 OOP changes, clasi 0.20260715.2):

**Every OOP change was blocked.** In all 3 OOP changes, Claude Code (running as team-lead) was blocked by `role-guard` from writing source files directly:

> "the team-lead role-guard hook blocked me from editing source directly even in OOP mode, so I routed the edit through a programmer agent"
> — Claude Code during OOP 1

> "I had to route the close-report write through a programmer agent — the team-lead role-guard blocks direct team-lead writes"
> — Claude Code during Sprint 002 close

> "Right now there's no in-progress ticket, no `.clasi/oop` file, and 'let's just get this done' isn't the explicit 'out of process' signal the rules require — so I can't silently make the edit."
> — Claude Code during OOP 2

**No `.clasi/oop` flag was ever created.** Throughout the entire 4-sprint run, neither `.clasi/oop` nor the legacy `.clasi-oop` flag file was created or used. The OOP prompts from `oop.sh` ("Let's just get this done", "Do this now without a sprint", etc.) were not recognized as OOP triggers by the enforcement system.

**Guards ARE enforcing.** The guards themselves are working correctly — 104 `role-guard` entries were logged, zero of them were `0 no-path` (the dead-gate signature from sprint 019). Actual `2 blk-write` blocks were recorded against sprint-planner agents:

```
19:45:38Z role-guard  2 blk-write  tool_name=Write  agent_type=sprint-planner
19:48:03Z role-guard  2 blk-write  tool_name=Write
19:49:01Z role-guard  2 blk-write  tool_name=Write
```

The problem is not that guards fail — the problem is that the **sanctioned escape hatch doesn't open**.

## Impact

- Team-lead agents cannot perform quick out-of-process edits. Every change must go through a programmer sub-agent, adding ~3-5 turns per OOP change.
- The OOP workflow documented in CLASI's skills and rules (`oop.md`, `.claude/rules/`) is non-functional.
- In run 003, all 3 OOP changes had to be routed through programmer agents — defeating the purpose of OOP mode (speed, simplicity, no ceremony).

## Root cause hypothesis

The `role-guard` handler in `hook_handlers.py` checks for the OOP flag file before allowing bypass, but either:

1. The flag file path check is wrong (guards check `.clasi-oop`, docs promise `.clasi/oop`, or vice versa — the split-brain documented in sprint 019 may still exist)
2. The detection logic requires the flag file to exist **before** the `claude -p` session starts, but the e2e workflow sends OOP prompts to already-running sessions that don't have the flag
3. The prompt-based OOP detection ("out of process" signal in the prompt text) isn't implemented or isn't triggering

## Steps to reproduce

1. Run CLASI in a project with enforcement guards active (clasi ≥ 0.20260715.2)
2. Start a `claude -p` session as team-lead
3. Attempt to edit a source file directly (Write/Edit tool) without an in-progress ticket and without a `.clasi/oop` flag file
4. The edit is blocked by `role-guard` with `2 blk-write`
5. Create `.clasi/oop` flag file: the edit succeeds

## Expected behavior

An OOP prompt (`oop.sh` output or explicit "out of process" instruction) should either:
- Be recognized by the enforcement system as an OOP signal, OR
- Automatically create the `.clasi/oop` flag file before attempting the edit

## Related

- Sprint 019: enforcement guards fail-open fix (made guards active, but OOP bypass was not verified)
- `clasi/sprints/019-.../issues/enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md` — item 5 documents the `.clasi-oop` vs `.clasi/oop` split-brain
- `clasi/issues/done/e2e-test-plan-002-guessing-game.md` — full e2e run 003 findings

## Additional context from e2e run 003

Other issues found in the same test run (see the e2e issue for full details):
- **Planning still too heavy:** 1,300–2,300 word sprint plans with Mermaid diagrams for a trivial 3-game CLI
- **Version bump noise:** 11 bumps in 36 commits (~1 per ticket)
- **No issue linkage:** All `issues:` fields remain empty
- **Close ceremony turn cost:** `close_sprint` burns 10+ turns, frequently hitting turn limits