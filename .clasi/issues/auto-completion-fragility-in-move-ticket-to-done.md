---
status: pending
---

# Auto-completion of issues in `move_ticket_to_done` only fires when the moved ticket has an `issue:` ref

## Context

`move_ticket_to_done` in [clasi/tools/artifact_tools.py:692-744](clasi/tools/artifact_tools.py) has an auto-completion step that moves an issue to `<sprint>/issues/done/` when all its referencing tickets are done. The logic at lines 719-742:

```python
todo_refs = ticket.issue_ref
if todo_refs is not None:
    for todo_filename in todo_list:
        todo = project.get_issue(todo_filename)
        if todo.status != "in-progress":
            continue
        ref_tickets = todo.tickets
        all_done = all(_is_ticket_done(ref_ticket_id) for ref_ticket_id in ref_tickets)
        if all_done and ref_tickets:
            ...
            todo.move_to_done()
```

The whole block is **guarded by `ticket.issue_ref is not None`** at line 721. If the just-moved ticket has no `issue:` ref, this code never runs — even if completing that ticket is what unblocks the issue.

Observed in sprint 001: T001 had `issue: plan-sprint-scoped-...`. T002, T003, T004 had `issue: ""`. The issue's `tickets:` listed all four. When T001 was moved-to-done, T002/T003/T004 were still open, so `all_done` was false, no relocation. When T002/T003/T004 were moved-to-done later, the guard at line 721 short-circuited (no `issue_ref`), so the check never ran. The issue stayed `in-progress` until manual `move_issue_to_done`.

The close-sprint precondition is the safety net (it self-repairs or hard-fails), but the happy path is broken.

## Goal

Auto-completion should fire whenever moving a ticket to done could plausibly complete an issue, regardless of whether the moved ticket itself is the one linked to that issue.

## Proposed approach

In `move_ticket_to_done`, after the ticket is moved:

1. **Scan the sprint's in-progress issues** (both `<sprint>/issues/*.md` top level and any pending-pool issues with `sprint == sprint_id`).
2. For each in-progress issue, check `all(_is_ticket_done(ticket_id) for ticket_id in todo.tickets)`.
3. If all done and not suppressed by `completes_issue: false`, relocate to `done/`.

This makes the per-ticket move idempotent with respect to issue completion: completing any ticket may surface a now-done issue, regardless of whether the ticket references it.

## Files to read

- [clasi/tools/artifact_tools.py:692-744](clasi/tools/artifact_tools.py) — current implementation, the guard at 721 is the bug
- [clasi/tools/artifact_tools.py:100-153](clasi/tools/artifact_tools.py) — `_is_ticket_done`, `_any_ticket_suppresses_todo`, `_todo_is_deferred` (utilities to reuse)
- [clasi/sprint.py:168-182](clasi/sprint.py) — `Sprint.list_issues` (returns both `issues/` and `issues/done/`)
- [tests/unit/test_issue_lifecycle.py](tests/unit/test_issue_lifecycle.py) — where the end-to-end coverage lives

## Interaction with related work

- This issue assumes [propagate-issue-refs-across-sprint-tickets.md](propagate-issue-refs-across-sprint-tickets.md) **is not** a prerequisite. The fragility fix should work even when tickets have empty `issue:` refs. If the propagation fix lands first, this issue becomes lower-priority but still worth fixing for robustness.
- The close-sprint precondition pass already implements this scan logic at [artifact_tools.py:985-1024](clasi/tools/artifact_tools.py). Consider extracting it into a shared helper `_sweep_done_issues(sprint)` that both `move_ticket_to_done` and `_close_sprint_full` call.

## Out of scope

- Changing the `issue:` frontmatter schema or back-references on the issue.
- Performance: scanning all sprint issues on every `move_ticket_to_done` is O(n_issues) per call. For sprints with <20 issues this is negligible; if it becomes a concern, index on the state DB.

## Verification

- After moving the **last** ticket that completes an issue (regardless of whether *that ticket* has `issue:` ref), the issue is auto-moved to `<sprint>/issues/done/` with `status: done`.
- Idempotent: calling `move_ticket_to_done` on a ticket whose issue is already done doesn't error.
- Respects `completes_issue: false` — if any sprint ticket suppresses the issue, no auto-completion.
- The existing happy-path test (single ticket with `issue:` ref → move → issue done) still passes.
- Manual end-to-end: simulate sprint 001 scenario (T001 has ref, T2-T4 don't); after the last `move_ticket_to_done`, the issue is relocated.
