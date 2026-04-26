---
status: done
sprint: 009
tickets:
- 009-001
---
# Bug: `close_sprint` auto-moves linked TODOs to `done/` even when the TODO spans multiple sprints

**CLASI version:** 0.20260410.1 (server) / 0.20260418.1 (CLI)

## Summary

When `close_sprint` finishes a sprint, it moves every TODO file linked to any ticket in that sprint from `docs/clasi/todo/` to `docs/clasi/todo/done/`. This is correct for single-sprint TODOs but wrong for **umbrella / multi-sprint TODOs** — long-lived plans that a sequence of sprints consumes across many months.

Concretely: if a master refactor TODO like `pike13-module-refactor-plan.md` enumerates tickets R-1 through R-8, Sprint A lands R-1/R-2/R-3 and its tickets link back to the master TODO. Closing Sprint A then archives the master TODO even though R-4 through R-8 haven't been touched yet.

## Observed behavior

From `close_sprint`'s JSON response after closing sprint 002:

```json
{
  "moved_todos": [
    "pike13-module-refactor-plan.md",
    "pike13-reports-models.md",
    "pike13-synchronization-strategy.md"
  ],
  "version": "0.20260418.2"
}
```

All three TODOs were supposed to remain pending — each one covers 2–3 future sprints of work. `move_ticket_to_done` exhibits the same behavior earlier in the ticket lifecycle: moving the last linked ticket of a sprint to `done/` archives the TODO file too.

## Why it matters

Two forced workarounds for stakeholders doing multi-sprint plans:

1. **Don't link tickets to the umbrella TODO.** But then CLASI loses the traceability from ticket → motivating plan, which is exactly what the linkage is for.
2. **Manually restore the TODO from `done/` after every sprint close.** This is what we did; it produced noise commits like `Restore multi-sprint TODOs to pending (post close_sprint)` and is error-prone (forgetting to restore breaks future sprint planning).

## Repro

1. Create two TODOs in `docs/clasi/todo/`:
   - `feature-a-small.md` (single-sprint)
   - `program-b-multi.md` (multi-sprint umbrella)
2. Plan a sprint whose tickets all set `todo: [feature-a-small.md, program-b-multi.md]`.
3. Complete all tickets. Close the sprint.
4. Observe: both TODOs move to `done/`, despite `program-b-multi.md` still having unexecuted scope.

## Proposed fixes (any one is sufficient)

1. **Opt-in field on ticket frontmatter.** `completes_todo: true|false` per linked filename. Default `true` (current behavior). Multi-sprint plans set `false` to keep the TODO pending after the sprint closes. Cleanest — decision lives with the ticket, where the author already knows.

2. **Opt-in field on TODO frontmatter.** Add `multi_sprint: true` to the TODO's YAML; `close_sprint` refuses to archive TODOs with that flag. Moves the decision to the TODO author.

3. **Explicit TODO close step.** `close_sprint` stops auto-moving TODOs entirely; stakeholders call `move_todo_to_done(filename)` themselves when the TODO is truly done. Matches the invariant "TODO completion ≠ ticket completion". Most flexible, biggest behavior change.

4. **Heuristic: only auto-archive TODOs linked to every ticket of every sprint that references them.** Requires cross-sprint awareness in `close_sprint` and is hard to reason about; probably not worth the complexity.

My preference: #1 (frontmatter flag on the ticket). Minimal change, backward-compatible, keeps the default behavior right for the common case.

## Related

See also `clasi#13` — `close_sprint` MCP tool schema is missing the documented `test_command` parameter. Same tool, different failure mode.
