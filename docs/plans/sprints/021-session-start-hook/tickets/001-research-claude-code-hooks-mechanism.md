---
id: "001"
title: "Research Claude Code hooks mechanism"
status: todo
use-cases: [SUC-001]
depends-on: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Research Claude Code hooks mechanism

## Description

Before building the session-start hook, we need to understand the exact
mechanism available in the current version of Claude Code. This is a
research ticket — the output is knowledge, not code.

Tasks:

1. **Read Claude Code documentation** — Determine how hooks are
   configured (e.g., `.claude/settings.local.json`, a dedicated
   `.claude/hooks/` directory, or another mechanism).
2. **Review Superpowers `session-start.sh`** — Examine how the
   Superpowers project implements its session-start hook. Note the
   format, trigger point, and how output is surfaced to the agent.
3. **Determine the correct format** — Document which hook type to use,
   what file(s) to create, and how the hook output reaches the agent
   context.
4. **Write findings** — Record the decision in a ticket plan file or
   notes section so ticket 002 can implement without guessing.

This ticket produces no code changes. It de-risks ticket 002 by
resolving unknowns up front.

## Acceptance Criteria

- [ ] Hook mechanism is documented (where hooks live, how they are configured)
- [ ] Correct format for a session-start hook is confirmed (file format, trigger type, output handling)
- [ ] Superpowers `session-start.sh` approach has been reviewed and findings recorded
- [ ] Decision doc or notes exist (in ticket plan or sprint notes) for ticket 002 to reference

## Testing

- **Existing tests to run**: `uv run pytest` (no regressions — no code changes expected)
- **New tests to write**: None (research ticket; no code modified)
- **Verification command**: `uv run pytest`
